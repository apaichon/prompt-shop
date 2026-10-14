package catalog

import "context"

// Retry runs op once more when it fails and the caller context is still active.
func Retry(ctx context.Context, op func(context.Context) error) error {
	err := op(ctx)
	if err == nil || ctx.Err() != nil {
		return err
	}
	return op(ctx)
}
