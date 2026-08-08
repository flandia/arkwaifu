package updateloop

import (
	"bytes"
	"context"
	"fmt"
	"github.com/alitto/pond"
	"github.com/chai2010/webp"
	"github.com/flandiayingman/arkwaifu/internal/app/art"
	"github.com/flandiayingman/arkwaifu/internal/pkg/ark"
	"github.com/flandiayingman/arkwaifu/internal/pkg/arkassets"
	"github.com/flandiayingman/arkwaifu/internal/pkg/arkprocessor"
	"github.com/flandiayingman/arkwaifu/internal/pkg/arkscanner"
	"github.com/flandiayingman/arkwaifu/internal/pkg/cols"
	"github.com/rs/zerolog/log"
	"os"
	"runtime"
	"time"
)

var (
	artPatterns = []string{
		"avg/imgs/**",
		"avg/images/**",
		"avg/bg/**",
		"avg/items/**",
		"avg/characters/**",
	}
)

type task func() error

func (s *Service) getRemoteArtVersion(ctx context.Context) (ark.Version, error) {
	return arkassets.GetLatestVersion()
}
func (s *Service) getLocalArtVersion(ctx context.Context) (ark.Version, error) {
	return s.repo.selectArtVersion(ctx)
}

func (s *Service) attemptUpdateArt(ctx context.Context) {
	localArtVersion, err := s.getLocalArtVersion(ctx)
	if err != nil {
		log.Error().
			Err(err).
			Caller().
			Msg("Failed to get the local art version.")
		return
	}
	remoteArtVersion, err := s.getRemoteArtVersion(ctx)
	if err != nil {
		log.Error().
			Err(err).
			Caller().
			Msg("Failed to get the remote art version.")
		return
	}
	if localArtVersion != remoteArtVersion {
		err := s.updateArts(ctx, localArtVersion, remoteArtVersion)
		if err != nil {
			log.Error().
				Err(err).
				Str("localArtVersion", localArtVersion).
				Str("remoteArtVersion", remoteArtVersion).
				Msg("Failed to update arts")
		}
	}
}

func (s *Service) updateArts(ctx context.Context, oldVersion, newVersion string) error {
	root, err := os.MkdirTemp("", "arkwaifu-updateloop-art-*")
	if err != nil {
		return err
	}
	defer func() { _ = os.RemoveAll(root) }()

	err = arkassets.UpdateGameAssets(ctx, oldVersion, newVersion, root, artPatterns)
	if err != nil {
		return err
	}

	pictureArtTasks, err := s.createPictureArtSubmitTasks(root)
	if err != nil {
		return err
	}
	characterArtTasks, err := s.createCharacterArtSubmitTasks(root)
	if err != nil {
		return err
	}

	workerNum := runtime.NumCPU()
	taskNum := len(pictureArtTasks) + len(characterArtTasks)
	log.Info().Msgf("Begin submitting arts, using %v workers to run %d tasks", workerNum, taskNum)

	begin := time.Now()
	pool := pond.New(workerNum, taskNum)
	defer pool.Stop()
	group, _ := pool.GroupContext(ctx)
	for _, artTask := range pictureArtTasks {
		group.Submit(artTask)
	}
	for _, artTask := range characterArtTasks {
		group.Submit(artTask)
	}
	err = group.Wait()
	if err != nil {
		return err
	}

	err = s.repo.upsertArtVersion(ctx, &artVersion{
		Lock:    zeroPtr,
		Version: newVersion,
	})
	if err != nil {
		return err
	}

	log.Info().Msgf("End submitting arts, elapsed %v", time.Since(begin))
	return nil
}

func (s *Service) createPictureArtSubmitTasks(root string) (tasks []task, err error) {
	scanner := arkscanner.Scanner{Root: root}

	pictureArts, err := scanner.ScanForPictureArts()
	if err != nil {
		return nil, err
	}

	for _, art := range pictureArts {
		tasks = append(tasks, s.createPictureArtSubmitTask(root, art))
	}

	return
}
func (s *Service) createPictureArtSubmitTask(root string, art *arkscanner.PictureArt) task {
	return func() error {
		log.Info().Msgf("Submitting the picture art %v...", *art)
		err := s.submitPictureArt(root, art)
		if err != nil {
			return fmt.Errorf("failed to submit picture art %v: %w", art, err)
		}
		return nil
	}
}
func (s *Service) submitPictureArt(root string, pic *arkscanner.PictureArt) error {
	processor := arkprocessor.Processor{Root: root}
	img, err := processor.ProcessPictureArt((*arkprocessor.PictureArt)(pic))
	if err != nil {
		return err
	}

	err = s.artService.UpsertArts(art.NewArt(img.Art.ID, art.MustParseCategory(img.Art.Kind)))
	if err != nil {
		return err
	}

	err = s.artService.UpsertVariants(art.NewVariant(img.Art.ID, art.VariationOrigin))
	if err != nil {
		return err
	}

	var buf bytes.Buffer
	err = webp.Encode(&buf, img.Image, &webp.Options{Lossless: true})
	if err != nil {
		return err
	}
	err = s.artService.StoreContent(img.Art.ID, art.VariationOrigin, buf.Bytes())
	if err != nil {
		return err
	}

	return nil
}

func (s *Service) createCharacterArtSubmitTasks(root string) (tasks []task, err error) {
	scanner := arkscanner.Scanner{Root: root}

	characterArts, err := scanner.ScanForCharacterArts()
	if err != nil {
		return nil, err
	}

	for _, art := range characterArts {
		tasks = append(tasks, s.createCharacterArtSubmitTask(root, art))
	}

	return
}
func (s *Service) createCharacterArtSubmitTask(root string, art *arkscanner.CharacterArt) task {
	return func() error {
		log.Info().Msgf("Submitting the character art %v...", *art)
		err := s.submitCharacterArt(root, art)
		if err != nil {
			return fmt.Errorf("failed to submit picture art %v: %w", art, err)
		}
		return nil
	}
}
func (s *Service) submitCharacterArt(root string, char *arkscanner.CharacterArt) error {
	processor := arkprocessor.Processor{Root: root}
	imgs, err := processor.ProcessCharacterArt((*arkprocessor.CharacterArt)(char))
	if err != nil {
		return err
	}
	if len(imgs) == 0 {
		return nil
	}

	err = s.artService.UpsertArts(cols.Map(imgs, func(img arkprocessor.CharacterArtImage) *art.Art {
		return art.NewArt(img.ID(), art.MustParseCategory(img.Art.Kind))
	})...)
	if err != nil {
		return err
	}

	err = s.artService.UpsertVariants(cols.Map(imgs, func(img arkprocessor.CharacterArtImage) *art.Variant {
		return art.NewVariant(img.ID(), art.VariationOrigin)
	})...)
	if err != nil {
		return err
	}

	for _, img := range imgs {
		var buf bytes.Buffer
		err := webp.Encode(&buf, img.Image, &webp.Options{Lossless: true})
		if err != nil {
			return err
		}
		err = s.artService.StoreContent(img.ID(), art.VariationOrigin, buf.Bytes())
		if err != nil {
			return err
		}
	}
	return nil
}
