"""Provides wrappers for the endpoints of the GDMC HTTP interface.

It is recommended to use the higher-level `editor.Editor` class instead.
"""


from typing import Sequence, Tuple, Optional, List, Dict, Any
from functools import partial
import time
from urllib.parse import urlparse

from glm import ivec2, ivec3
import requests
from requests.exceptions import ConnectionError as RequestConnectionError
from termcolor import colored

from . import __url__
from .utility import eprint, withRetries
from .vector_tools import Box
from .block import Block


DEFAULT_HOST = "http://localhost:9000"


class InterfaceError(RuntimeError):
    """An error occured when communicating with the GDMC HTTP interface"""


class InterfaceConnectionError(InterfaceError):
    """An error occured when trying to connect to the GDMC HTTP interface"""


class InterfaceInternalError(InterfaceError):
    """The GDMC HTTP interface reported an internal server error (500)"""


class BuildAreaNotSetError(InterfaceError):
    """Attempted to retieve the build area while it was not set"""


def _onRequestRetry(e: Exception, retriesLeft: int):
    eprint(colored(color="yellow", text=\
         "HTTP request failed!\n"
         "Error:\n"
        f"{e}\n"
        f"I'll retry in a bit ({retriesLeft} retries left)."
    ))
    time.sleep(3)


def _request(method: str, url: str, *args, retries: int, **kwargs):
    try:
        response = withRetries(partial(requests.request, method, url, *args, **kwargs), retries=retries, onRetry=_onRequestRetry)
    except RequestConnectionError as e:
        u = urlparse(url)
        raise InterfaceConnectionError(
            f"Could not connect to the GDMC HTTP interface at {u.scheme}://{u.netloc}.\n"
             "To use GDPC, you need to use a \"backend\" that provides the GDMC HTTP interface.\n"
             "For example, by running Minecraft with the GDMC HTTP mod installed.\n"
            f"See {__url__}/README.md for more information."
        ) from e

    if response.status_code == 500:
        raise InterfaceInternalError("The GDMC HTTP interface reported an internal server error (500)")

    return response


def getBlocks(position: ivec3, size: Optional[ivec3] = None, dimension: Optional[str] = None, includeState=False, includeData=False, retries=0, timeout=None, host=DEFAULT_HOST):
    """Returns the blocks in the specified region.

    <dimension> can be one of {"overworld", "the_nether", "the_end"} (default "overworld").

    Returns a list of (position, block)-tuples.

    If a set of coordinates is invalid, the returned block ID will be "minecraft:void_air".
    """
    url = f"{host}/blocks"
    dx, dy, dz = (None, None, None) if size is None else size
    parameters = {
        'x': position.x,
        'y': position.y,
        'z': position.z,
        'dx': dx,
        'dy': dy,
        'dz': dz,
        'includeState': True if includeState else None,
        'includeData':  True if includeData  else None,
        'dimension': dimension
    }
    response = _request("GET", url, params=parameters, headers={"accept": "application/json"}, retries=retries, timeout=timeout)
    blockDicts: List[Dict[str, Any]] = response.json()
    # TODO: deal with b.get("data")
    if includeData:
        raise NotImplementedError("includeData is still a work-in-progress.")
    return [(ivec3(b["x"], b["y"], b["z"]), Block(b["id"], b.get("state", {}))) for b in blockDicts]


def placeBlocks(blocks: Sequence[Tuple[ivec3, Block]], dimension: Optional[str] = None, doBlockUpdates=True, spawnDrops=False, customFlags: str = "", retries=0, timeout=None, host=DEFAULT_HOST):
    """Places blocks in the world.

    Each element of <blocks> should be a tuple (position, block). The blocks must each describe
    exactly one block: palettes or "no placement" blocks are not allowed.

    <dimension> can be one of {"overworld", "the_nether", "the_end"} (default "overworld").

    The <doBlockUpdates>, <spawnDrops> and <customFlags> parameters control block update
    behavior. See the GDMC HTTP API documentation for more info.

    Returns a list with one string for each block placement. If the block placement was
    successful, the string is "1" if the block changed, or "0" otherwise. If the placement
    failed, it is the error message.
    """
    url = f"{host}/blocks"

    blockStr = "\n".join(
        f"{pos.x} {pos.y} {pos.z} "
        f"{block.id + block.blockStateString() + (f'{{{block.data}}}' if block.data else '')}" for pos, block in blocks
    )

    if customFlags != "":
        blockUpdateParams = {"customFlags": customFlags}
    else:
        blockUpdateParams = {"doBlockUpdates": doBlockUpdates, "spawnDrops": spawnDrops}

    parameters = {"dimension": dimension}
    parameters.update(blockUpdateParams)

    return _request("PUT", url, data=bytes(blockStr, "utf-8"), params=parameters, retries=retries, timeout=timeout).text.split("\n")


def runCommand(command: str, dimension: Optional[str] = None, retries=0, timeout=None, host=DEFAULT_HOST):
    """Executes one or multiple Minecraft commands (separated by newlines).

    The leading "/" must be omitted.

    <dimension> can be one of {"overworld", "the_nether", "the_end"} (default "overworld").

    Returns a list with one string for each command. If the command was successful, the string
    is its return value. Otherwise, it is the error message.
    """
    url = f"{host}/command"
    return _request("POST", url, bytes(command, "utf-8"), params={'dimension': dimension}, retries=retries, timeout=timeout).text.split("\n")


def getBuildArea(retries=0, timeout=None, host=DEFAULT_HOST):
    """Retrieves the build area that was specified with /setbuildarea in-game.

    Fails if the build area was not specified yet.

    Returns (success, result).
    If a build area was specified, result is the box describing the build area.
    Otherwise, result is the error message string.
    """
    response = _request("GET", f"{host}/buildarea", retries=retries, timeout=timeout)

    if not response.ok or response.json() == -1:
        raise BuildAreaNotSetError(
            "Failed to get the build area.\n"
            "Make sure to set the build area with /setbuildarea in-game.\n"
            "For example: /setbuildarea ~0 0 ~0 ~128 255 ~128"
        )

    buildAreaJson = response.json()
    fromPoint = ivec3(
        buildAreaJson["xFrom"],
        buildAreaJson["yFrom"],
        buildAreaJson["zFrom"]
    )
    toPoint = ivec3(
        buildAreaJson["xTo"],
        buildAreaJson["yTo"],
        buildAreaJson["zTo"]
    )
    return Box.between(fromPoint, toPoint)


def getChunks(position: ivec2, size: Optional[ivec2] = None, dimension: Optional[str] = None, asBytes=False, retries=0, timeout=None, host=DEFAULT_HOST):
    """Returns raw chunk data.

    <position> specifies the position in chunk coordinates, and <size> specifies how many chunks
    to get in each axis (default 1).
    <dimension> can be one of {"overworld", "the_nether", "the_end"} (default "overworld").

    If <asBytes> is True, returns raw binary data. Otherwise, returns a human-readable
    representation.

    On error, returns the error message instead.
    """
    url = f"{host}/chunks"
    dx, dz = (None, None) if size is None else size
    parameters = {
        "x": position.x,
        "z": position.y,
        "dx": dx,
        "dz": dz,
        "dimension": dimension,
    }
    acceptType = "application/octet-stream" if asBytes else "text/plain"
    response = _request("GET", url, params=parameters, headers={"Accept": acceptType}, retries=retries, timeout=timeout)
    return response.content if asBytes else response.text


def getVersion(retries=0, timeout=None, host=DEFAULT_HOST):
    """Returns the Minecraft version as a string."""
    return _request("GET", f"{host}/version", retries=retries, timeout=timeout).text
