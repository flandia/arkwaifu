package updateloop

import (
	"context"
	"os"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/Jeffail/gabs/v2"
	"github.com/flandiayingman/arkwaifu/internal/app/gallery"
	"github.com/flandiayingman/arkwaifu/internal/pkg/ark"
	"github.com/flandiayingman/arkwaifu/internal/pkg/arkdata"
	"github.com/flandiayingman/arkwaifu/internal/pkg/arkjson"
	"github.com/pkg/errors"
	"github.com/rs/zerolog/log"
)

var (
	galleryPatterns = []string{
		"gamedata/excel/activity_table.json",
		"gamedata/excel/story_review_meta_table.json",
		"gamedata/excel/replicate_table.json",
		"gamedata/excel/retro_table.json",
		"gamedata/excel/roguelike_topic_table.json",
		"gamedata/excel/stage_table.json",
	}
)

func (s *Service) getRemoteGalleryVersion(ctx context.Context, server ark.Server) (ark.Version, error) {
	v, err := arkdata.GetLatestCompositeDataVersion(ctx, server)
	if err != nil {
		return "", err
	}
	return v.ResourceVersion, nil
}

func (s *Service) getLocalGalleryVersion(ctx context.Context, server ark.Server) (ark.Version, error) {
	return s.repo.selectGalleryVersion(ctx, server)
}

func (s *Service) attemptUpdateGalleries(ctx context.Context, server ark.Server) {
	log := log.With().
		Str("server", server).
		Logger()
	log.Info().Msg("Attempting to update galleries of the server. ")
	localVersion, err := s.getLocalGalleryVersion(ctx, server)
	if err != nil {
		log.Err(err).
			Msg("Failed to get the local gallery version of the server. ")
		return
	}
	remoteVersion, err := s.getRemoteGalleryVersion(ctx, server)
	if err != nil {
		log.Err(err).
			Msg("Failed to get the remote gallery version of the server. ")
		return
	}
	log = log.With().
		Str("localVersion", localVersion).
		Str("remoteVersion", remoteVersion).
		Logger()
	if localVersion != remoteVersion {
		log.Info().Msg("Updating the stories of the server, since the gallery versions are not identical. ")
		begin := time.Now()
		err = s.updateGalleries(ctx, server, remoteVersion)
		if err != nil {
			log.Err(err).Msg("Update loop failed to update the stories")
		}
		log.Info().
			Str("elapsed", time.Since(begin).String()).
			Msg("Updated the stories of the server successfully. ")
	} else {
		log.Info().Msg("Skip updating the stories of the server, since the gallery versions are identical. ")
	}
}

func (s *Service) updateGalleries(ctx context.Context, server ark.Server, version ark.Version) error {
	root, err := os.MkdirTemp("", "arkwaifu-updateloop-gallery-*")
	if err != nil {
		return err
	}
	defer os.RemoveAll(root)

	err = arkdata.GetCompositeGameData(ctx, server, version, galleryPatterns, root)
	if err != nil {
		return err
	}

	galleries, err := ParseToGalleries(server, root)
	if err != nil {
		return err
	}

	err = s.galleryService.Put(galleries)
	if err != nil {
		return errors.WithStack(err)
	}

	err = s.repo.upsertGalleryVersion(ctx, &galleryVersion{
		Server:  server,
		Version: version,
	})
	if err != nil {
		return err
	}

	return nil
}

func ParseToGalleries(server ark.Server, root string) ([]gallery.Gallery, error) {
	jsonStoryReviewMetaTable, err := arkjson.Get(root, arkjson.StoryReviewMetaTablePath)
	if err != nil {
		return nil, err
	}
	jsonRetroTable, err := arkjson.Get(root, arkjson.RetroTable)
	if err != nil {
		return nil, err
	}
	jsonReplicateTable, err := arkjson.Get(root, arkjson.ReplicateTable)
	if err != nil {
		return nil, err
	}
	jsonRoguelikeTopicTable, err := arkjson.Get(root, arkjson.RoguelikeTopicTable)
	if err != nil {
		return nil, err
	}
	jsonStageTable, err := arkjson.Get(root, arkjson.StageTable)
	if err != nil && !os.IsNotExist(err) {
		return nil, err
	}
	jsonActivityTable, err := arkjson.Get(root, arkjson.ActivityTable)
	if err != nil && !os.IsNotExist(err) {
		return nil, err
	}

	artMap := make(map[string]gallery.Art)
	for _, c := range jsonStoryReviewMetaTable.S("actArchiveResData", "pics").Children() {
		artMap[strings.ToLower(c.S("id").Data().(string))] = gallery.Art{
			Server:      server,
			GalleryID:   "", // Auto Generated
			SortID:      0,
			ID:          strings.ToLower(c.S("id").Data().(string)),
			Name:        c.S("desc").Data().(string),
			Description: c.S("picDescription").Data().(string),
			ArtID:       strings.ToLower(c.S("assetPath").Data().(string)),
		}
	}

	galleryDescriptions := make(map[string]string)
	if jsonStageTable != nil {
		for _, c := range jsonStageTable.S("storylineStorySets").Children() {
			id := strings.ToLower(stringOrEmpty(c.S("relevantActivityId").Data()))
			if id == "" {
				continue
			}
			galleryDescriptions[id] = storySetDescription(c)
		}
	}

	galleryMap := make(map[string]gallery.Gallery)
	for _, c := range jsonRetroTable.S("retroActList").Children() {
		for _, actID := range c.S("linkedActId").Children() {
			id := strings.ToLower(stringOrEmpty(actID.Data()))
			description := stringOrEmpty(c.S("detail").Data())
			if description == "" {
				description = galleryDescriptions[id]
			}
			galleryMap[id] = gallery.Gallery{
				Server:      server,
				ID:          id,
				Name:        c.S("name").Data().(string),
				Description: description,
				Arts:        nil,
			}
		}
	}
	for _, c := range jsonRoguelikeTopicTable.S("topics").Children() {
		galleryMap[strings.ToLower(c.S("id").Data().(string))] = gallery.Gallery{
			Server:      server,
			ID:          strings.ToLower(c.S("id").Data().(string)),
			Name:        c.S("name").Data().(string),
			Description: c.S("lineText").Data().(string),
			Arts:        nil,
		}
	}

	galleriesByID := make(map[string]gallery.Gallery)
	for id, c := range jsonStoryReviewMetaTable.Search("actArchiveData", "components").ChildrenMap() {
		if jsonReplicateTable.Exists(id) {
			continue
		}
		galleryID := strings.ToLower(id)
		if gallery, ok := galleryMap[galleryID]; ok {
			for _, pic := range c.S("pic", "pics").Children() {
				art, ok := artMap[strings.ToLower(stringOrEmpty(pic.S("picId").Data()))]
				if !ok {
					continue
				}
				art.GalleryID = galleryID
				art.SortID = int(pic.S("picSortId").Data().(float64))
				gallery.Arts = append(gallery.Arts, art)
			}
			galleriesByID[galleryID] = gallery
		}
	}

	if jsonStageTable != nil {
		mergeCGGalleries(server, jsonStageTable, jsonActivityTable, jsonReplicateTable, galleryMap, galleriesByID)
	}

	galleries := make([]gallery.Gallery, 0, len(galleriesByID))
	for _, gallery := range galleriesByID {
		galleries = append(galleries, gallery)
	}
	sort.Slice(galleries, func(i, j int) bool {
		return galleries[i].ID < galleries[j].ID
	})

	return galleries, nil
}

func mergeCGGalleries(
	server ark.Server,
	stageTable *gabs.Container,
	activityTable *gabs.Container,
	replicateTable *gabs.Container,
	galleryMetadata map[string]gallery.Gallery,
	galleriesByID map[string]gallery.Gallery,
) {
	usedArtIDs := make(map[string]struct{})
	for _, currentGallery := range galleriesByID {
		for _, art := range currentGallery.Arts {
			usedArtIDs[art.ID] = struct{}{}
		}
	}

	groups := stageTable.S("cgGalleryGroups").ChildrenMap()
	groupIDs := make([]string, 0, len(groups))
	for groupID := range groups {
		groupIDs = append(groupIDs, groupID)
	}
	sort.Strings(groupIDs)

	for _, groupID := range groupIDs {
		group := groups[groupID]
		storySet := stageTable.S("storylineStorySets", groupID)
		galleryID := strings.ToLower(stringOrEmpty(storySet.S("relevantActivityId").Data()))
		if galleryID == "" || replicateTable.Exists(galleryID) {
			continue
		}

		currentGallery, ok := galleriesByID[galleryID]
		if !ok {
			currentGallery, ok = galleryMetadata[galleryID]
		}
		if !ok {
			name := activityName(activityTable, galleryID)
			if name == "" {
				continue
			}
			currentGallery = gallery.Gallery{
				Server: server,
				ID:     galleryID,
				Name:   name,
			}
		}
		if currentGallery.Name == "" {
			currentGallery.Name = activityName(activityTable, galleryID)
		}
		if currentGallery.Description == "" {
			currentGallery.Description = storySetDescription(storySet)
		}

		artIndexByAssetID := make(map[string]int, len(currentGallery.Arts))
		nextSortID := 0
		for i := range currentGallery.Arts {
			artIndexByAssetID[currentGallery.Arts[i].ArtID] = i
			if currentGallery.Arts[i].SortID > nextSortID {
				nextSortID = currentGallery.Arts[i].SortID
			}
		}

		for _, displayIDContainer := range group.S("displays").Children() {
			displayID := stringOrEmpty(displayIDContainer.Data())
			if displayID == "" {
				continue
			}
			display := stageTable.S("cgGalleryDisplays", displayID)
			displayName := stringOrEmpty(display.S("displayName").Data())
			displayDescription := stringOrEmpty(display.S("displayDesc").Data())

			for cgIndex, cgIDContainer := range display.S("cgList").Children() {
				assetID := strings.ToLower(stringOrEmpty(cgIDContainer.Data()))
				if assetID == "" {
					continue
				}
				if artIndex, exists := artIndexByAssetID[assetID]; exists {
					if currentGallery.Arts[artIndex].Name == "" {
						currentGallery.Arts[artIndex].Name = displayName
					}
					if currentGallery.Arts[artIndex].Description == "" {
						currentGallery.Arts[artIndex].Description = displayDescription
					}
					continue
				}

				nextSortID++
				id := uniqueGalleryArtID(
					strings.ToLower(displayID)+"_"+strconv.Itoa(cgIndex+1),
					usedArtIDs,
				)
				currentGallery.Arts = append(currentGallery.Arts, gallery.Art{
					Server:      server,
					GalleryID:   galleryID,
					SortID:      nextSortID,
					ID:          id,
					Name:        displayName,
					Description: displayDescription,
					ArtID:       assetID,
				})
				artIndexByAssetID[assetID] = len(currentGallery.Arts) - 1
			}
		}

		galleriesByID[galleryID] = currentGallery
	}
}

func activityName(activityTable *gabs.Container, activityID string) string {
	if activityTable == nil {
		return ""
	}
	return stringOrEmpty(activityTable.S("basicInfo", activityID, "name").Data())
}

func storySetDescription(storySet *gabs.Container) string {
	for _, path := range [][]string{
		{"ssData", "desc"},
		{"mainlineData", "desc"},
		{"collectData", "desc"},
	} {
		if description := stringOrEmpty(storySet.S(path...).Data()); description != "" {
			return description
		}
	}
	return ""
}

func uniqueGalleryArtID(base string, used map[string]struct{}) string {
	id := base
	for suffix := 2; ; suffix++ {
		if _, exists := used[id]; !exists {
			used[id] = struct{}{}
			return id
		}
		id = base + "_" + strconv.Itoa(suffix)
	}
}

func stringOrEmpty(value interface{}) string {
	stringValue, _ := value.(string)
	return stringValue
}
