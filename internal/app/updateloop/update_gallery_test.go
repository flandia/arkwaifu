package updateloop

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/flandiayingman/arkwaifu/internal/app/gallery"
	"github.com/flandiayingman/arkwaifu/internal/pkg/ark"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestParseToGalleriesAllowsMissingRetroDetail(t *testing.T) {
	root := t.TempDir()

	writeGalleryFixture(t, root, "story_review_meta_table.json", `{
  "actArchiveResData": {
    "pics": {
      "pic1": {
        "id": "pic1",
        "desc": "Picture 1",
        "picDescription": "",
        "assetPath": "asset1"
      }
    }
  },
  "actArchiveData": {
    "components": {
      "act1": {
        "pic": {
          "pics": {
            "pic1": {
              "picId": "pic1",
              "picSortId": 1
            }
          }
        }
      }
    }
  }
}`)
	writeGalleryFixture(t, root, "retro_table.json", `{
  "retroActList": {
    "retro1": {
      "linkedActId": ["act1"],
      "name": "Gallery 1"
    }
  }
}`)
	writeGalleryFixture(t, root, "replicate_table.json", `{}`)
	writeGalleryFixture(t, root, "roguelike_topic_table.json", `{"topics": {"0": {}, "1": null}}`)
	writeGalleryFixture(t, root, "stage_table.json", `{
  "storylineStorySets": {
    "set1": {
      "relevantActivityId": "act1",
      "ssData": {
        "desc": "Stage description"
      }
    }
  }
}`)

	galleries, err := ParseToGalleries(ark.CnServer, root)

	require.NoError(t, err)
	require.Len(t, galleries, 1)
	assert.Equal(t, "act1", galleries[0].ID)
	assert.Equal(t, "Gallery 1", galleries[0].Name)
	assert.Equal(t, "Stage description", galleries[0].Description)
	require.Len(t, galleries[0].Arts, 1)
}

func TestParseToGalleriesMergesCGGallerySchema(t *testing.T) {
	root := t.TempDir()

	writeGalleryFixture(t, root, "story_review_meta_table.json", `{
  "actArchiveResData": {
    "pics": {
      "legacy_shared": {
        "id": "legacy_shared",
        "desc": "Legacy shared picture",
        "picDescription": "",
        "assetPath": "70_i01_2"
      },
      "legacy_only": {
        "id": "legacy_only",
        "desc": "Legacy-only picture",
        "picDescription": "Legacy-only description",
        "assetPath": "legacy_only_asset"
      }
    }
  },
  "actArchiveData": {
    "components": {
      "act49side": {
        "pic": {
          "pics": {
            "legacy_shared": {"picId": "legacy_shared", "picSortId": 1},
            "legacy_only": {"picId": "legacy_only", "picSortId": 2}
          }
        }
      }
    }
  }
}`)
	writeGalleryFixture(t, root, "retro_table.json", `{
  "retroActList": {
    "retro1": {
      "linkedActId": ["act49side"],
      "name": "辞岁行"
    }
  }
}`)
	writeGalleryFixture(t, root, "replicate_table.json", `{}`)
	writeGalleryFixture(t, root, "roguelike_topic_table.json", `{"topics": {}}`)
	writeGalleryFixture(t, root, "activity_table.json", `{
  "basicInfo": {
    "act49side": {"name": "辞岁行"}
  }
}`)
	writeGalleryFixture(t, root, "stage_table.json", `{
  "storylineStorySets": {
    "setId_ssLine_act49side": {
      "relevantActivityId": "act49side",
      "ssData": {"desc": "一柄尘封的书刀"}
    }
  },
  "cgGalleryGroups": {
    "setId_ssLine_act49side": {
      "storySetId": "setId_ssLine_act49side",
      "displays": ["cgId_ssLine_act49side_1"]
    }
  },
  "cgGalleryDisplays": {
    "cgId_ssLine_act49side_1": {
      "displayId": "cgId_ssLine_act49side_1",
      "cgList": ["70_i01_2", "70_i01_1", "70_i01_3"],
      "displayName": "竹简之味",
      "displayDesc": "嘿嘿，那这道菜就叫",
      "storySetId": "setId_ssLine_act49side",
      "sortId": 1
    }
  }
}`)

	galleries, err := ParseToGalleries(ark.CnServer, root)

	require.NoError(t, err)
	require.Len(t, galleries, 1)
	assert.Equal(t, "一柄尘封的书刀", galleries[0].Description)
	require.Len(t, galleries[0].Arts, 4)

	shared := galleryArtByArtID(t, galleries[0].Arts, "70_i01_2")
	assert.Equal(t, "legacy_shared", shared.ID)
	assert.Equal(t, "Legacy shared picture", shared.Name)
	assert.Equal(t, "嘿嘿，那这道菜就叫", shared.Description)

	legacyOnly := galleryArtByArtID(t, galleries[0].Arts, "legacy_only_asset")
	assert.Equal(t, "Legacy-only picture", legacyOnly.Name)
	assert.Equal(t, "Legacy-only description", legacyOnly.Description)

	for _, artID := range []string{"70_i01_1", "70_i01_3"} {
		art := galleryArtByArtID(t, galleries[0].Arts, artID)
		assert.Equal(t, "竹简之味", art.Name)
		assert.Equal(t, "嘿嘿，那这道菜就叫", art.Description)
	}
}

func TestParseToGalleriesAddsCGOnlyGallery(t *testing.T) {
	root := t.TempDir()

	writeGalleryFixture(t, root, "story_review_meta_table.json", `{
  "actArchiveResData": {"pics": {}},
  "actArchiveData": {"components": {}}
}`)
	writeGalleryFixture(t, root, "retro_table.json", `{"retroActList": {}}`)
	writeGalleryFixture(t, root, "replicate_table.json", `{}`)
	writeGalleryFixture(t, root, "roguelike_topic_table.json", `{"topics": {}}`)
	writeGalleryFixture(t, root, "activity_table.json", `{
  "basicInfo": {
    "act49side": {"name": "辞岁行"}
  }
}`)
	writeGalleryFixture(t, root, "stage_table.json", `{
  "storylineStorySets": {
    "setId_ssLine_act49side": {
      "relevantActivityId": "act49side",
      "ssData": {"desc": "一柄尘封的书刀"}
    }
  },
  "cgGalleryGroups": {
    "setId_ssLine_act49side": {
      "storySetId": "setId_ssLine_act49side",
      "displays": ["cgId_ssLine_act49side_1"]
    }
  },
  "cgGalleryDisplays": {
    "cgId_ssLine_act49side_1": {
      "displayId": "cgId_ssLine_act49side_1",
      "cgList": ["70_i01_2"],
      "displayName": "竹简之味",
      "displayDesc": "嘿嘿，那这道菜就叫",
      "storySetId": "setId_ssLine_act49side",
      "sortId": 1
    }
  }
}`)

	galleries, err := ParseToGalleries(ark.CnServer, root)

	require.NoError(t, err)
	require.Len(t, galleries, 1)
	assert.Equal(t, "act49side", galleries[0].ID)
	assert.Equal(t, "辞岁行", galleries[0].Name)
	assert.Equal(t, "一柄尘封的书刀", galleries[0].Description)
	require.Len(t, galleries[0].Arts, 1)
	assert.Equal(t, "70_i01_2", galleries[0].Arts[0].ArtID)
}

func galleryArtByArtID(t *testing.T, arts []gallery.Art, artID string) gallery.Art {
	t.Helper()
	for _, art := range arts {
		if art.ArtID == artID {
			return art
		}
	}
	require.FailNowf(t, "art not found", "artID %q", artID)
	return gallery.Art{}
}

func writeGalleryFixture(t *testing.T, root, name, content string) {
	t.Helper()

	path := filepath.Join(root, "assets", "torappu", "dynamicassets", "gamedata", "excel", name)
	require.NoError(t, os.MkdirAll(filepath.Dir(path), 0o755))
	require.NoError(t, os.WriteFile(path, []byte(content), 0o600))
}
