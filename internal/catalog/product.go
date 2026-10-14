package catalog

// Label is a stored aisle or shelf id plus its plain-text label.
type Label struct {
	ID    string `json:"id"`
	Label string `json:"label"`
}

// Product is formed only from stored product, shelf, and aisle rows.
type Product struct {
	ID             string `json:"id"`
	Name           string `json:"name"`
	Category       string `json:"category"`
	Aisle          Label  `json:"aisle"`
	Shelf          Label  `json:"shelf"`
	RouteAvailable bool   `json:"route_available"`
}

// Indexed is one published product plus the alias texts used for ranking.
type Indexed struct {
	Product Product
	Aliases []string
	NodeID  string
}
