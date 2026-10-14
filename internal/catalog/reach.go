package catalog

// Reachable returns every node connected to origin by an undirected edge.
func Reachable(origin string, from, to []string) map[string]bool {
	adj := make(map[string][]string, len(from))
	for i := range from {
		adj[from[i]] = append(adj[from[i]], to[i])
		adj[to[i]] = append(adj[to[i]], from[i])
	}
	seen := map[string]bool{}
	if origin == "" {
		return seen
	}
	seen[origin] = true
	queue := []string{origin}
	for len(queue) > 0 {
		n := queue[0]
		queue = queue[1:]
		for _, next := range adj[n] {
			if !seen[next] {
				seen[next] = true
				queue = append(queue, next)
			}
		}
	}
	return seen
}
