"""Polygon oracle independent of the application's importer/routing code."""
EPS = 1e-9


def cross(a, b):
    return a[0]*b[1]-a[1]*b[0]


def on_segment(point, start, end):
    direction = (end[0]-start[0], end[1]-start[1])
    offset = (point[0]-start[0], point[1]-start[1])
    return abs(cross(direction, offset)) <= EPS and min(start[0], end[0])-EPS <= point[0] <= max(start[0], end[0])+EPS and min(start[1], end[1])-EPS <= point[1] <= max(start[1], end[1])+EPS


def strictly_inside(point, polygon):
    vertices = [(p["x"], p["y"]) for p in polygon]
    inside = False
    for a, b in zip(vertices, vertices[1:]+vertices[:1]):
        if on_segment(point, a, b):
            return False
        if (a[1] > point[1]) != (b[1] > point[1]):
            x = a[0]+(point[1]-a[1])*(b[0]-a[0])/(b[1]-a[1])
            if x > point[0]:
                inside = not inside
    return inside


def crosses_interior(start, end, polygon):
    a, b = (start["x"], start["y"]), (end["x"], end["y"])
    if strictly_inside(a, polygon) or strictly_inside(b, polygon):
        return True
    d = (b[0]-a[0], b[1]-a[1])
    cuts = {0.0, 1.0}
    vertices = [(p["x"], p["y"]) for p in polygon]
    for c, e in zip(vertices, vertices[1:]+vertices[:1]):
        edge = (e[0]-c[0], e[1]-c[1])
        delta = (c[0]-a[0], c[1]-a[1])
        denominator = cross(d, edge)
        if abs(denominator) > EPS:
            t, u = cross(delta, edge)/denominator, cross(delta, d)/denominator
            if -EPS <= t <= 1+EPS and -EPS <= u <= 1+EPS:
                cuts.add(max(0, min(1, t)))
        elif abs(cross(delta, d)) <= EPS:
            axis = 0 if abs(d[0]) >= abs(d[1]) else 1
            if abs(d[axis]) > EPS:
                for v in (c, e):
                    t = (v[axis]-a[axis])/d[axis]
                    if 0 <= t <= 1:
                        cuts.add(t)
    ordered = sorted(cuts)
    return any(strictly_inside((a[0]+d[0]*(left+right)/2, a[1]+d[1]*(left+right)/2), polygon)
               for left, right in zip(ordered, ordered[1:]) if right-left > EPS)


def reachable(origin, edges):
    adjacency = {}
    for edge in edges:
        a, b = edge["from_node_id"], edge["to_node_id"]
        adjacency.setdefault(a, set()).add(b)
        adjacency.setdefault(b, set()).add(a)
    seen, todo = set(), [origin]
    while todo:
        node = todo.pop()
        if node in seen:
            continue
        seen.add(node)
        todo.extend(adjacency.get(node, set())-seen)
    return seen
