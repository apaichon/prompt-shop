package importer

import (
	"math"
	"sort"
)

const epsilon = 1e-9

func cross(a, b, c Point) float64 { return (b.X-a.X)*(c.Y-a.Y) - (b.Y-a.Y)*(c.X-a.X) }
func onSegment(p, a, b Point) bool {
	return math.Abs(cross(a, b, p)) < epsilon && p.X >= math.Min(a.X, b.X)-epsilon && p.X <= math.Max(a.X, b.X)+epsilon && p.Y >= math.Min(a.Y, b.Y)-epsilon && p.Y <= math.Max(a.Y, b.Y)+epsilon
}

// Boundaries are walkable; fixture interiors are not.
func inside(p Point, poly []Point) bool {
	in := false
	for i, a := range poly {
		b := poly[(i+1)%len(poly)]
		if onSegment(p, a, b) {
			return false
		}
		if (a.Y > p.Y) != (b.Y > p.Y) && p.X < (b.X-a.X)*(p.Y-a.Y)/(b.Y-a.Y)+a.X {
			in = !in
		}
	}
	return in
}
func intersects(a, b, c, d Point) bool {
	return cross(a, b, c)*cross(a, b, d) < 0 && cross(c, d, a)*cross(c, d, b) < 0 || onSegment(a, c, d) || onSegment(b, c, d) || onSegment(c, a, b) || onSegment(d, a, b)
}
func simplePolygon(p []Point) bool {
	area := 0.0
	for i, a := range p {
		b := p[(i+1)%len(p)]
		if a == b {
			return false
		}
		area += a.X*b.Y - b.X*a.Y
		for j := i + 1; j < len(p); j++ {
			if j == i+1 || i == 0 && j == len(p)-1 {
				continue
			}
			if intersects(a, b, p[j], p[(j+1)%len(p)]) {
				return false
			}
		}
	}
	return math.Abs(area) > epsilon
}

// Split the segment at every boundary intersection, including vertices and
// collinear overlaps, and inspect each interval. This handles concave polygons.
func crossesInterior(a, b Point, p []Point) bool {
	ts := []float64{0, 1}
	dx, dy := b.X-a.X, b.Y-a.Y
	if math.Abs(dx)+math.Abs(dy) < epsilon {
		return inside(a, p)
	}
	for i, c := range p {
		d := p[(i+1)%len(p)]
		ex, ey := d.X-c.X, d.Y-c.Y
		den := dx*ey - dy*ex
		if math.Abs(den) > epsilon {
			t := ((c.X-a.X)*ey - (c.Y-a.Y)*ex) / den
			u := ((c.X-a.X)*dy - (c.Y-a.Y)*dx) / den
			if t >= 0 && t <= 1 && u >= 0 && u <= 1 {
				ts = append(ts, t)
			}
		} else {
			for _, v := range []Point{c, d} {
				if onSegment(v, a, b) {
					var t float64
					if math.Abs(dx) > math.Abs(dy) {
						t = (v.X - a.X) / dx
					} else {
						t = (v.Y - a.Y) / dy
					}
					ts = append(ts, t)
				}
			}
		}
	}
	sort.Float64s(ts)
	for i := 1; i < len(ts); i++ {
		t := (ts[i-1] + ts[i]) / 2
		if inside(Point{a.X + t*dx, a.Y + t*dy}, p) {
			return true
		}
	}
	return false
}
