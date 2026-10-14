package catalog

import (
	"github.com/gofiber/fiber/v2"
)

// Failure is a documented API error. Product is set only for a truthful
// route-unavailable location, never for an unknown or unpublished id.
type Failure struct {
	Status    int
	Code      string
	Message   string
	Retryable bool
	Product   *Product
}

func writeFailure(c *fiber.Ctx, f Failure) error {
	errBody := map[string]any{
		"code":      f.Code,
		"message":   f.Message,
		"retryable": f.Retryable,
	}
	if f.Product != nil {
		errBody["details"] = map[string]any{"product": f.Product}
	}
	if f.Status == fiber.StatusTooManyRequests {
		c.Set("Retry-After", "1")
	}
	return c.Status(f.Status).JSON(fiber.Map{
		"error":      errBody,
		"request_id": c.GetRespHeader("X-Request-ID"),
	})
}

func dependencyFailure() Failure {
	return Failure{Status: fiber.StatusServiceUnavailable, Code: "DEPENDENCY_UNAVAILABLE", Message: "database unavailable", Retryable: true}
}

func invalidRequest(message string) Failure {
	return Failure{Status: fiber.StatusBadRequest, Code: "INVALID_REQUEST", Message: message, Retryable: false}
}
