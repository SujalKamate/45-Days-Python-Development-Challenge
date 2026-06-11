"""
Abstract Base Class Shape Hierarchy with Polymorphism Demonstration
Defines abstract Shape; implements Circle, Rectangle, Triangle; demonstrates polymorphism.
"""

import math
from abc import ABC, abstractmethod
from typing import List


# ── Abstract Base Class ───────────────────────────────────────────────────────
class Shape(ABC):
    """Abstract base class for all geometric shapes."""

    def __init__(self, color: str = "white", filled: bool = False):
        self.color  = color
        self.filled = filled

    @abstractmethod
    def area(self) -> float:
        """Return the area of the shape."""

    @abstractmethod
    def perimeter(self) -> float:
        """Return the perimeter of the shape."""

    @abstractmethod
    def describe(self) -> str:
        """Return a human-readable description."""

    def __str__(self):
        return (f"{self.__class__.__name__}("
                f"area={self.area():.4f}, "
                f"perimeter={self.perimeter():.4f}, "
                f"color={self.color})")

    def __repr__(self):
        return self.__str__()

    def scale(self, factor: float) -> "Shape":
        """Return a new scaled version of this shape."""
        raise NotImplementedError(f"{self.__class__.__name__} does not support scaling.")

    def is_larger_than(self, other: "Shape") -> bool:
        return self.area() > other.area()

    def aspect_info(self) -> str:
        return f"Area={self.area():.4f}, Perimeter={self.perimeter():.4f}"


# ── Circle ────────────────────────────────────────────────────────────────────
class Circle(Shape):
    def __init__(self, radius: float, color: str = "white", filled: bool = False):
        if radius <= 0:
            raise ValueError("Radius must be positive.")
        super().__init__(color, filled)
        self.radius = radius

    def area(self) -> float:
        return math.pi * self.radius ** 2

    def perimeter(self) -> float:
        return 2 * math.pi * self.radius

    def circumference(self) -> float:
        return self.perimeter()

    def diameter(self) -> float:
        return 2 * self.radius

    def describe(self) -> str:
        return (f"Circle: radius={self.radius}, "
                f"diameter={self.diameter():.4f}, "
                f"circumference={self.circumference():.4f}, "
                f"area={self.area():.4f}")

    def scale(self, factor: float) -> "Circle":
        return Circle(self.radius * factor, self.color, self.filled)

    def inscribed_square_side(self) -> float:
        return self.radius * math.sqrt(2)


# ── Rectangle ─────────────────────────────────────────────────────────────────
class Rectangle(Shape):
    def __init__(self, width: float, height: float, color: str = "white", filled: bool = False):
        if width <= 0 or height <= 0:
            raise ValueError("Width and height must be positive.")
        super().__init__(color, filled)
        self.width  = width
        self.height = height

    def area(self) -> float:
        return self.width * self.height

    def perimeter(self) -> float:
        return 2 * (self.width + self.height)

    def diagonal(self) -> float:
        return math.sqrt(self.width ** 2 + self.height ** 2)

    def is_square(self) -> bool:
        return math.isclose(self.width, self.height)

    def aspect_ratio(self) -> float:
        return self.width / self.height

    def describe(self) -> str:
        square_note = " (Square)" if self.is_square() else ""
        return (f"Rectangle{square_note}: {self.width}×{self.height}, "
                f"diagonal={self.diagonal():.4f}, "
                f"area={self.area():.4f}")

    def scale(self, factor: float) -> "Rectangle":
        return Rectangle(self.width * factor, self.height * factor, self.color, self.filled)


class Square(Rectangle):
    def __init__(self, side: float, color: str = "white", filled: bool = False):
        super().__init__(side, side, color, filled)
        self.side = side

    def describe(self) -> str:
        return (f"Square: side={self.side}, "
                f"diagonal={self.diagonal():.4f}, "
                f"area={self.area():.4f}")

    def scale(self, factor: float) -> "Square":
        return Square(self.side * factor, self.color, self.filled)


# ── Triangle ──────────────────────────────────────────────────────────────────
class Triangle(Shape):
    def __init__(self, a: float, b: float, c: float, color: str = "white", filled: bool = False):
        if a <= 0 or b <= 0 or c <= 0:
            raise ValueError("All sides must be positive.")
        if not (a + b > c and b + c > a and a + c > b):
            raise ValueError(f"Sides {a}, {b}, {c} don't form a valid triangle.")
        super().__init__(color, filled)
        self.a, self.b, self.c = a, b, c

    def area(self) -> float:
        s = self.perimeter() / 2
        return math.sqrt(s * (s - self.a) * (s - self.b) * (s - self.c))

    def perimeter(self) -> float:
        return self.a + self.b + self.c

    def kind(self) -> str:
        sides = sorted([self.a, self.b, self.c])
        if math.isclose(sides[0], sides[1]) and math.isclose(sides[1], sides[2]):
            return "Equilateral"
        if math.isclose(sides[0], sides[1]) or math.isclose(sides[1], sides[2]):
            return "Isosceles"
        return "Scalene"

    def is_right(self) -> bool:
        s = sorted([self.a ** 2, self.b ** 2, self.c ** 2])
        return math.isclose(s[0] + s[1], s[2], rel_tol=1e-5)

    def height_from_base(self, base=None) -> float:
        base = base or self.a
        return 2 * self.area() / base

    def describe(self) -> str:
        return (f"Triangle ({self.kind()}{'|Right' if self.is_right() else ''}): "
                f"sides={self.a},{self.b},{self.c}, "
                f"area={self.area():.4f}")

    def scale(self, factor: float) -> "Triangle":
        return Triangle(self.a * factor, self.b * factor, self.c * factor, self.color, self.filled)


# ── Ellipse ───────────────────────────────────────────────────────────────────
class Ellipse(Shape):
    def __init__(self, semi_major: float, semi_minor: float, color="white", filled=False):
        if semi_major <= 0 or semi_minor <= 0:
            raise ValueError("Semi-axes must be positive.")
        super().__init__(color, filled)
        self.a = semi_major
        self.b = semi_minor

    def area(self) -> float:
        return math.pi * self.a * self.b

    def perimeter(self) -> float:
        # Ramanujan approximation
        h = ((self.a - self.b) / (self.a + self.b)) ** 2
        return math.pi * (self.a + self.b) * (1 + 3*h / (10 + math.sqrt(4 - 3*h)))

    def eccentricity(self) -> float:
        if self.a >= self.b:
            return math.sqrt(1 - (self.b/self.a)**2)
        return math.sqrt(1 - (self.a/self.b)**2)

    def describe(self) -> str:
        return (f"Ellipse: a={self.a}, b={self.b}, "
                f"eccentricity={self.eccentricity():.4f}, "
                f"area={self.area():.4f}")

    def scale(self, factor: float) -> "Ellipse":
        return Ellipse(self.a * factor, self.b * factor, self.color, self.filled)


# ── Polymorphism demo ─────────────────────────────────────────────────────────
def total_area(shapes: List[Shape]) -> float:
    return sum(s.area() for s in shapes)


def largest_shape(shapes: List[Shape]) -> Shape:
    return max(shapes, key=lambda s: s.area())


def print_shape_table(shapes: List[Shape]):
    print(f"\n  {'═'*70}")
    print(f"  {'Shape':<20} {'Area':>12} {'Perimeter':>12} {'Color':<10} {'Filled'}")
    print(f"  {'─'*70}")
    for s in shapes:
        print(f"  {s.__class__.__name__:<20} {s.area():>12.4f} {s.perimeter():>12.4f} "
              f"{s.color:<10} {str(s.filled)}")
    print(f"  {'─'*70}")
    print(f"  {'Total Area':>33} {total_area(shapes):>12.4f}")
    print(f"  {'═'*70}\n")


def main():
    print("╔══════════════════════════════════════════╗")
    print("║   Abstract Shape Hierarchy v1.0         ║")
    print("╚══════════════════════════════════════════╝")

    shapes: List[Shape] = [
        Circle(5, color="red", filled=True),
        Circle(3, color="blue"),
        Rectangle(4, 7, color="green", filled=True),
        Square(6, color="yellow"),
        Triangle(3, 4, 5, color="orange", filled=True),
        Triangle(5, 5, 5, color="purple"),
        Ellipse(6, 4, color="teal"),
    ]

    print("\n  Shape Descriptions (polymorphic .describe()):")
    for s in shapes:
        print(f"  • {s.describe()}")

    print_shape_table(shapes)

    big = largest_shape(shapes)
    print(f"  Largest shape: {big.__class__.__name__} with area={big.area():.4f}")

    print("\n  Scaling demo (factor=2):")
    for s in shapes[:4]:
        scaled = s.scale(2)
        print(f"  {s.__class__.__name__}  orig area={s.area():.3f}  scaled={scaled.area():.3f}  "
              f"ratio={scaled.area()/s.area():.1f}×")

    print("\n  Triangle properties:")
    tris = [Triangle(3,4,5), Triangle(5,5,5), Triangle(3,4,6)]
    for t in tris:
        print(f"  {t.describe()}  right={t.is_right()}  height={t.height_from_base():.4f}")

    print("\n  Sorted by area (ascending):")
    for s in sorted(shapes, key=lambda x: x.area()):
        print(f"  {s.__class__.__name__:<15} {s.area():>10.4f}")

    print("\n  Polymorphism: iterate mixed list and call same methods")
    mixed: List[Shape] = [Circle(2), Rectangle(3, 4), Triangle(6, 8, 10), Square(5), Ellipse(7, 3)]
    for s in mixed:
        print(f"  {type(s).__name__:<15} area={s.area():.3f}  perim={s.perimeter():.3f}")


if __name__ == "__main__":
    main()
