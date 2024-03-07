from __future__ import annotations

from typing import Tuple

import jax
from jax import Array
import jax.numpy as jnp
from flax import struct

from .registry import SpritesRegistry, TILE_SIZE, SPRITES_REGISTRY


class RenderingCache(struct.PyTreeNode):
    patches: Array
    """A flat set of patches representing the RGB values of each tile in the base map"""

    @classmethod
    def init(cls, grid: Array) -> RenderingCache:
        background = render_background(grid)
        patches = flatten_patches(background)

        # add discard pile
        patches = jnp.concatenate(
            [
                patches,
                jnp.zeros((1, TILE_SIZE, TILE_SIZE, 3), dtype=jnp.uint8),
            ],
            axis=0,
        )
        return cls(patches=patches)


def render_background(
    grid: Array, sprites_registry: SpritesRegistry = SPRITES_REGISTRY
) -> Array:
    image_width = grid.shape[0] * TILE_SIZE
    image_height = grid.shape[1] * TILE_SIZE
    n_channels = 3

    background = jnp.zeros((image_height, image_width, n_channels), dtype=jnp.uint8)
    grid_resized = jax.image.resize(
        grid, (grid.shape[0] * TILE_SIZE, grid.shape[1] * TILE_SIZE), method="nearest"
    )

    mask = jnp.asarray(grid_resized, dtype=bool)  # 0 = floor, 1 = wall
    # index by [entity_type, direction, open/closed, y, x, channel]
    wall_tile = tile_grid(grid, sprites_registry.get("wall"))
    floor_tile = tile_grid(grid, sprites_registry.get("floor"))
    background = jnp.where(mask[..., None], wall_tile, floor_tile)
    return background


def tile_grid(grid: Array, tile: Array) -> Array:
    """Tiles a grid (H, W) with equal tiles `tiles` (w, h, 3) to get a final array
    of shape (H * h, W * w, 3) and dtype `jnp.uint8`"""
    tiled = jnp.tile(tile, (*grid.shape, 1))
    return jnp.asarray(tiled, dtype=jnp.uint8)


def flatten_patches(
    image: Array, patch_size: Tuple[int, int] = (TILE_SIZE, TILE_SIZE)
) -> Array:
    height = image.shape[0] // patch_size[0]
    width = image.shape[1] // patch_size[1]
    n_channels = image.shape[2]

    grid = image.reshape(height, patch_size[0], width, patch_size[1], n_channels)

    # Swap the first and second axes of the grid to revert the stacking order
    grid = jnp.swapaxes(grid, 1, 2)

    # Reshape the grid of tiles into the original list of tiles
    patches = grid.reshape(height * width, patch_size[0], patch_size[1], n_channels)

    return patches


def unflatten_patches(patches: Array, image_size: Tuple[int, int]) -> Array:
    image_height = image_size[0]
    image_width = image_size[1]
    patch_height = patches.shape[1]
    patch_width = patches.shape[2]
    n_channels = patches.shape[3]

    # Reshape the list of tiles into a 2D grid
    grid = patches.reshape(
        image_height // patch_height,
        image_width // patch_width,
        patch_height,
        patch_width,
        n_channels,
    )

    # Swap the first and second axes of the grid to change the order of stacking
    grid = jnp.swapaxes(grid, 1, 2)

    # Reshape and stack the grid tiles horizontally and vertically to form the final image
    image = grid.reshape(image_height, image_width, n_channels)

    return image
