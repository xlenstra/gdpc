#! /usr/bin/python3
"""### Provides tools for creating multidimensional shapes."""
__all__ = ['placeLine', 'placeArea', 'placeCuboid', 'placefromList']
__version__ = 'v4.3_dev'

import lookup
import numpy as np
import toolbox
from interfaceUtils import globalinterface as gi


def placeLine(x1, y1, z1, x2, y2, z2, blocks, replace=None, interface=gi):
    """**Draw a line from point to point efficiently**."""
    settings = blocks, replace, interface
    dimension, flatSides = getDimension(x1, y1, z1, x2, y2, z2)
    if dimension == 0:
        return interface.placeBlock(x1, y1, z1, blocks, replace)
    elif dimension == 1:
        return placeArea(x1, y1, z1, x2, y2, z2, *settings)
    elif dimension == 2:
        axis = None
        if 'x' in flatSides:
            axis = 'x'
            line = line2d(y1, z1, y2, z2)
            pad = x1
        elif 'y' in flatSides:
            axis = 'y'
            line = line2d(x1, z1, x2, z2)
            pad = y1
        elif 'z' in flatSides:
            axis = 'z'
            line = line2d(x1, y1, x2, y2)
            pad = z1

        return placefromList(padDimension(line, pad, axis), *settings)
    elif dimension == 3:
        return placefromList(line3d(x1, y1, z1, x2, y2, z2), *settings)


def placeJointedLine(points, blocks, replace=None, interface=gi):
    return placefromList(lineSequence(points), blocks, replace, interface)


def placePolygon(points, blocks, replace=None, filled=False, interface=gi):
    polygon = set()
    polygon.update(lineSequence(points))
    polygon.update(line3d(*points[0], *points[-1]))
    dimension, vector = getDimension(*shapeboundries(polygon))
    if filled and dimension == 2:
        polygon.update(fill2d(polygon))
    elif filled and dimension == 3:
        print("Cannot ")


def placeArea(x1, y1, z1, x2, y2, z2, blocks, replace=None, interface=gi):
    """**Fill an area with blocks**."""
    buffering = interface.isBuffering()
    if not buffering:
        interface.setBuffering(True)
        result = placefromList(toolbox.loop3d(x1, y1, z1, x2, y2, z2),
                               blocks, replace, interface)
        interface.setBuffering(False)
        return result
    return placefromList(toolbox.loop3d(x1, y1, z1, x2, y2, z2),
                         blocks, replace, interface)


def placeCuboid(x1, y1, z1, x2, y2, z2, blocks, replace=None,
                hollow=False, interface=gi):
    """**Draw a cubic shape that fills the entire region."""
    settings = blocks, replace, interface
    dimension, _ = getDimension(x1, y1, z1, x2, y2, z2)

    if dimension == 0:                       # single block
        return interface.placeBlock(x1, y1, z1, blocks, replace)

    elif dimension in (1, 2) or not hollow:  # line, rectangle or solid cuboid
        return placeArea(x1, y1, z1, x2, y2, z2,  *settings)

    elif dimension == 3 and hollow:                         # hollow cuboid
        bottom = placeArea(x1, y1, z1, x2, y1, z2, *settings)      # bottom
        top = placeArea(x1, y2, z1, x2, y2, z2, *settings)         # top
        north = placeArea(x1, y1, z1, x1, y2, z2, *settings)       # north
        south = placeArea(x2, y1, z1, x2, y2, z2, *settings)       # south
        west = placeArea(x1, y1, z1, x2, y2, z1, *settings)        # west
        east = placeArea(x1, y1, z2, x2, y2, z2, *settings)        # east
        try:
            return bottom + top + north + south + west + east
        except TypeError:
            return (f'{lookup.TCOLORS["orange"]}Errors while drawing hollow '
                    f'cuboid:\n\tTop {top}\n\tBottom {bottom}\n\t'
                    f'North {north}\n\tSouth {south}\n\t'
                    f'West {west}\n\tEast {east}')


def placeCylinder(x1, y1, z1, x2, y2, z2, blocks, replace=None,
                  axis='y', hollow=False, interface=gi):
    """**Draw a cylindric shape that fills the entire region."""
    settings = blocks, replace, interface
    dimension, flatSides = getDimension(x1, y1, z1, x2, y2, z2)

    def placeCylinderBody(a1, b1, a2, b2, h0, hn):
        """**Build a cylinder**."""
        tube, base = ellipse(a1, b1, a2, b2, filled=True)
        base = padDimension(base, h0, axis)
        if hollow:
            tube = padDimension(tube, h0, axis)
        else:
            tube = base

        bottom = placefromList(base,  *settings)
        top = 0
        body = 0
        if h0 != hn:
            top = placefromList(transform(base, hn - h0, axis),  *settings)
            body = placefromList(repeat(tube, hn - h0 - 2, axis), *settings)

        try:
            return bottom + top + body
        except TypeError:
            return (f'{lookup.TCOLORS["orange"]}Errors while drawing '
                    f'cylinder:\n\tBase {bottom}\n\tTop {top}\n\tBody {body}')

    if dimension == 0:
        return interface.placeBlock(x1, y1, z1, blocks, replace)
    elif (dimension == 1
          or (len(flatSides) > 0 and flatSides[0] != axis)):
        return placeArea(x1, y1, z1, x2, y2, z2, *settings)
    elif dimension == 2:
        if flatSides == ['x']:
            return placeCylinderBody(y1, z1, y2, z2, x1, x2)
        elif flatSides == ['y']:
            return placeCylinderBody(x1, z1, x2, z2, y1, y2)
        elif flatSides == ['z']:
            return placeCylinderBody(x1, y1, x2, y2, z1, z2)
        raise ValueError(f'{lookup.TCOLORS["red"]}Unexpected shape!')
    elif dimension == 3:
        if axis == 'x':
            return placeCylinderBody(y1, z1, y2, z2, x1, x2)
        elif axis == 'y':
            return placeCylinderBody(x1, z1, x2, z2, y1, y2)
        elif axis == 'z':
            return placeCylinderBody(x1, y1, x2, y2, z1, z2)
        raise ValueError(f'{lookup.TCOLORS["red"]}{axis} is not a valid axis!')


def placefromList(list, blocks, replace=None, interface=gi):
    """**Replace all blocks at coordinates in list with blocks**."""
    result = 0
    ERRORMESSAGE = (f"\n{lookup.TCOLORS['orange']}"
                    "Fails:\n{lookup.TCOLORS['gray']}")
    errors = ERRORMESSAGE
    for x, y, z in list:
        response = interface.placeBlock(x, y, z, blocks, replace)
        if response.isnumeric():
            result += int(response)
        else:
            errors += response + '\n'
    if errors is not ERRORMESSAGE:
        result = str(result) + errors
    return result

# ========================================================= calculations


def floodFill(x, y, z, axis='y', replace='minecraft:air'):
    """**Return the points for all connected blocks along a plain**."""
    if isinstance(replace, str):
        replace = (replace, )
    elif not toolbox.isSequence(replace):
        raise TypeError(f'{lookup.TCOLORS["red"]}{replace} is neither '
                        'a string nor a sequence!')

    raise NotImplementedError()


def transform(points, amount, axis='y'):
    points = set(points)
    vx, vy, vz = lookup.AXIS2VECTOR[axis]
    clone = [(x + amount * vx, y + amount * vy, z + amount * vz)
             for x, y, z in points]
    return clone


def repeat(points, times, axis='y', step=1):
    """**Return points with duplicates shifted along the appropriate axis**."""
    clone = set(points)
    for n in range(1, times + 2):
        clone.update(transform(points, step * n, axis))
    return clone


def fill2d(points):
    filling = points = list(points)
    minx, miny = np.array(filling).min(axis=0)
    maxx, maxy = np.array(filling).max(axis=0)
    cx, cy = minx + (maxx - minx) // 2, miny + (maxy - miny) // 2

    def fill(x, y):
        if (x, y) in points:
            return
        elif not (minx <= x <= maxx and miny <= y <= maxy):
            raise ValueError(f'{lookup.TCOLORS["red"]}Aborted filling '
                             'open-sided shape!')
        points.append((x, y))
        fill(x + 1, y)
        fill(x - 1, y)
        fill(x, y + 1)
        fill(x, y - 1)

    fill(cx, cy)
    return points


def fill3d(points):
    filling = points = list(points)
    minx, miny, minz = np.array(filling).min(axis=0)
    maxx, maxy, maxz = np.array(filling).max(axis=0)
    cx, cy, cz = (minx + (maxx - minx) // 2,
                  miny + (maxy - miny) // 2,
                  minz + (maxz - minz) // 2)

    def fill(x, y, z):
        if (x, y, z) in points:
            return
        elif not (minx <= x <= maxx
                  and miny <= y <= maxy
                  and minz <= z <= maxz):
            raise ValueError(f'{lookup.TCOLORS["red"]}Aborted filling '
                             'open-sided 3D shape!')
        points.append((x, y, z))
        fill(x + 1, y, z)
        fill(x - 1, y, z)
        fill(x, y + 1, z)
        fill(x, y - 1, z)
        fill(x, y, z + 1)
        fill(x, y, z - 1)

    fill(cx, cy, cz)
    return points


def getDimension(x1, y1, z1, x2, y2, z2):
    """**Determine the number of dimensions the input uses**."""
    if (x1, y1, z1) == (x2, y2, z2):
        return 0, list(lookup.AXES)
    # NOTE: if dimension needs to be known, return isdifferent
    isflat = np.subtract((x1, y1, z1), (x2, y2, z2)) == 0
    flatSides = []
    flatSides += ['x'] if isflat[0] else []
    flatSides += ['y'] if isflat[1] else []
    flatSides += ['z'] if isflat[2] else []
    return 3 - isflat.sum(), flatSides


def padDimension(points, value=0, axis='z'):
    """**Pad a list of 3D points with a value in the appropriate position**."""
    if axis == 'x':
        return [(value, i[0], i[-1]) for i in points]
    elif axis == 'y':
        return [(i[0], value, i[-1]) for i in points]
    elif axis == 'z':
        return [(i[0], i[1], value) for i in points]
    raise ValueError(f'{lookup.TCOLORS["red"]}{axis} is not a valid axis '
                     'to pad with!')


def cutDimension(points, axis='z'):
    try:
        if axis == 'x':
            return [(i[0:]) for i in points]
        elif axis == 'y':
            dimension = len(points[0])
            if dimension == 2:
                return [(i[:-1]) for i in points]
            elif dimension == 3:
                return [(i[0], i[-1]) for i in points]
        elif axis == 'z':
            return [(i[:-1]) for i in points]
    except IndexError:
        pass
    raise ValueError(f'{lookup.TCOLORS["red"]}{axis} is not a valid axis '
                     f'to cut from this set!\n{points}')


def shapeboundries(points):
    points = np.array(points)
    dimension = len(points[0])
    if dimension == 2:
        minx, miny = points.min(axis=0)
        maxx, maxy = points.max(axis=0)
        return minx, miny, maxx, maxy
    elif dimension == 3:
        minx, miny, minz = points.min(axis=0)
        maxx, maxy, maxz = points.max(axis=0)
        return minx, miny, minz, maxx, maxy, maxz
    else:
        raise ValueError(f'{lookup.TCOLORS["red"]}{dimension}D '
                         'shapes are not supported!')


def line2d(x1, y1, x2, y2):
    """**Return coordinates for a 2D line from point to point**.

    From
    https://www.codegrepper.com/code-examples/python/line+algorithm+in+python
    """
    dx = x2 - x1
    dy = y2 - y1
    is_steep = abs(dy) > abs(dx)
    if abs(dy) > abs(dx):
        x1, y1 = y1, x1
        x2, y2 = y2, x2

    # Swap start and end points if necessary
    if x1 > x2:
        x1, x2 = x2, x1
        y1, y2 = y2, y1

    dx = x2 - x1
    dy = y2 - y1

    # Calculate error
    error = int(dx / 2.0)
    ystep = 1 if y1 < y2 else -1

    # Iterate over bounding box generating points between start and end
    y = y1
    points = set()
    for x in range(x1, x2 + 1):
        coord = (y, x) if is_steep else (x, y)
        points.add(coord)
        error -= abs(dy)
        if error < 0:
            y += ystep
            error += dx

    return points


def line3d(x1, y1, z1, x2, y2, z2):
    """**Return coordinates for a 3D line from point to point**.

    With 'inspiration' from
    https://www.geeksforgeeks.org/bresenhams-algorithm-for-3-d-line-drawing/
    """

    def if_greater_pos_else_neg(a, b):
        return 1 if a > b else -1

    def bresenham_line_next_point(x, y, z, xs, ys, zs, dx, dy, dz, p1, p2):
        x += xs
        if (p1 >= 0):
            y += ys
            p1 -= 2 * dx
        if (p2 >= 0):
            z += zs
            p2 -= 2 * dx
        p1 += 2 * dy
        p2 += 2 * dz
        return x, y, z, p1, p2

    points = set()
    points.add((x1, y1, z1))
    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    dz = abs(z2 - z1)
    xs = if_greater_pos_else_neg(x2, x1)
    ys = if_greater_pos_else_neg(y2, y1)
    zs = if_greater_pos_else_neg(z2, z1)

    # Driving axis is X-axis"
    if (dx >= dy and dx >= dz):
        p1 = 2 * dy - dx
        p2 = 2 * dz - dx
        while (x1 != x2):
            x1, y1, z1, p1, p2 = bresenham_line_next_point(x1, y1, z1,
                                                           xs, ys, zs,
                                                           dx, dy, dz,
                                                           p1, p2)
            points.add((x1, y1, z1))

    # Driving axis is Y-axis"
    elif (dy >= dx and dy >= dz):
        p1 = 2 * dx - dy
        p2 = 2 * dz - dy
        while (y1 != y2):
            y1, x1, z1, p1, p2 = bresenham_line_next_point(y1, x1, z1,
                                                           ys, xs, zs,
                                                           dy, dx, dz,
                                                           p1, p2)
            points.add((x1, y1, z1))

    # Driving axis is Z-axis"
    else:
        p1 = 2 * dy - dz
        p2 = 2 * dx - dz
        while (z1 != z2):
            z1, x1, y1, p1, p2 = bresenham_line_next_point(z1, x1, y1,
                                                           zs, xs, ys,
                                                           dz, dx, dy,
                                                           p1, p2)
            points.add((x1, y1, z1))

    return points


def lineSequence(points):
    last = points[0]
    dimension = len(last)
    toPlace = set()
    for point in points[0:]:
        if dimension == 2:
            toPlace.update(line2d(*last, *point))
        elif dimension == 3:
            toPlace.update(line3d(*last, *point))
        else:
            raise ValueError(f'{lookup.TCOLORS["red"]}{dimension}D '
                             'lineSequence not supported!')
        last = point


def circle(x1, y1, x2, y2, filled=False):
    """**Return the points of a circle with a given centre and diameter**.

    With 'inspiration' from:
    https://www.geeksforgeeks.org/bresenhams-circle-drawing-algorithm/
    """
    toolbox.normaliseCoordinates(x1, y1, x2, y2)

    diameter = min(x2 - x1, y2 - y1)
    e = diameter % 2    # for even centers
    cx, cy = x1 + diameter // 2, y1 + diameter // 2
    points = set()

    def eightPoints(x, y):
        points.add((cx + e + x, cy + e + y))
        points.add((cx - 0 - x, cy + e + y))
        points.add((cx + e + x, cy - 0 - y))
        points.add((cx - 0 - x, cy - 0 - y))
        points.add((cx + e + y, cy + e + x))
        points.add((cx - 0 - y, cy + e + x))
        points.add((cx + e + y, cy - 0 - x))
        points.add((cx - 0 - y, cy - 0 - x))

    r = diameter // 2
    x, y = 0, r
    d = 3 - 2 * r
    eightPoints(x, y)
    while (y >= x):
        # for each pixel we will
        # draw all eight pixels

        x += 1

        # check for decision parameter
        # and correspondingly
        # update d, x, y
        if (d > 0):
            y -= 1
            d = d + 4 * (x - y) + 10
        else:
            d = d + 4 * x + 6
        eightPoints(x, y)

    if filled:
        return points, fill2d(points)
    return points


def ellipse(x1, y1, x2, y2, filled=False):
    """**Return the points of an ellipse with a given centre and size**.

    Modified version 'inspired' by chandan_jnu from
    https://www.geeksforgeeks.org/midpoint-ellipse-drawing-algorithm/
    """
    toolbox.normaliseCoordinates(x1, y1, x2, y2)

    dx, dy = x2 - x1, y2 - y1
    ex, ey = dx % 2, dy % 2
    if dx == dy:
        return circle(x1, y1, x2, y2, filled)
    cx, cy = x1 + dx / 2, y1 + dy / 2
    points = set()
    filledpoints = set()

    def fourpoints(x, y):
        points.add((cx + x, cy + y))
        points.add((cx - x, cy + y))
        points.add((cx + x, cy - y))
        points.add((cx - x, cy - y))

        if filled:
            filledpoints.update(line2d(cx + ex, cy + ey, cx + x, cy + y))
            filledpoints.update(line2d(cx, cy + ey, cx - x, cy + y))
            filledpoints.update(line2d(cx + ex, cy, cx + x, cy - y))
            filledpoints.update(line2d(cx, cy, cx - x, cy - y))

    rx, ry = dx / 2, dy / 2

    x = 0
    y = ry

    # Initial decision parameter of region 1
    d1 = ((ry * ry) - (rx * rx * ry) + (0.25 * rx * rx))
    dx = 2 * ry * ry * x
    dy = 2 * rx * rx * y

    # For region 1
    while (dx < dy):

        fourpoints(x, y)

        # Checking and updating value of
        # decision parameter based on algorithm
        if (d1 < 0):
            x += 1
            dx = dx + (2 * ry * ry)
            d1 = d1 + dx + (ry * ry)
        else:
            x += 1
            y -= 1
            dx = dx + (2 * ry * ry)
            dy = dy - (2 * rx * rx)
            d1 = d1 + dx - dy + (ry * ry)

    # Decision parameter of region 2
    d2 = (((ry * ry) * ((x + 0.5) * (x + 0.5)))
          + ((rx * rx) * ((y - 1) * (y - 1))) - (rx * rx * ry * ry))

    # Plotting points of region 2
    while (y >= 0):

        fourpoints(x, y)

        # Checking and updating parameter
        # value based on algorithm
        if (d2 > 0):
            y -= 1
            dy = dy - (2 * rx * rx)
            d2 = d2 + (rx * rx) - dy
        else:
            y -= 1
            x += 1
            dx = dx + (2 * ry * ry)
            dy = dy - (2 * rx * rx)
            d2 = d2 + dx - dy + (rx * rx)

    if filled:
        return points, fill2d(points)
    return points
