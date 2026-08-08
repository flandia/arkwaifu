package updateloop

import (
	"testing"

	"github.com/flandiayingman/arkwaifu/internal/pkg/util/pathutil"
)

func TestArtPatternsIncludeCurrentGalleryImageBundles(t *testing.T) {
	matched, err := pathutil.MatchAny(artPatterns, "avg/images/76_i01_2.ab")
	if err != nil {
		t.Fatalf("match art patterns: %v", err)
	}
	if !matched {
		t.Fatal("current avg/images gallery bundle path is not included in artPatterns")
	}
}
