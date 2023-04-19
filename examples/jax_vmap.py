import jax.numpy as jnp
import jax.random as jrd
import jax


# https://ericmjl.github.io/dl-workshop/02-jax-idioms/01-loopless-loops.html#exercise-chained-vmaps
# https://github.com/google/jax/discussions/5199
# https://github.com/google/jax/issues/673
# https://jax.readthedocs.io/en/latest/_autosummary/jax.vmap.html#jax.vmap

@jax.jit
def mini_test(x, base, target_offset):
    return jnp.sqrt(jnp.square(x[base] - x[10 + target_offset]))

def run_vvmap_test():
    vmap_mini_test = jax.vmap(mini_test, in_axes=(None, None, 0))
    vvmap_mini_test = jax.vmap(vmap_mini_test, in_axes=(None, 0, None))

    x = jnp.arange(10, 24)
    offsets = jnp.arange(start=0, stop=4, step=1)
    base_i = jnp.arange(start=0, stop=10, step=1)

    res = vvmap_mini_test(x, base_i, offsets)
    print(res)


# ============================================================================

def L2_dist(x, base, target_offset, d: int):
    # x[2:6] == jax.lax.dynamic_slice(x, (2,), (4,))
    diff = lax.dynamic_slice(x, (base,), (d,)) - lax.dynamic_slice(x, (target_offset, ), (d,))
    return jnp.sqrt(diff.dot(diff))
    return jnp.sqrt(jnp.square(x[base: base + d] - x[target_offset : target_offset + d]))


vmap_L2_dist = vmap(L2_dist, in_axes=(None, None, 0, None))
vvmap_L2_dist = vmap(vmap_L2_dist, in_axes=(None, 0, None, None))
jitted_L2_dist = jit(vvmap_L2_dist, static_argnames=['d'])

def genome_to_param(genome: jnp.ndarray, d: int = 1, layer_dimensions: list = [10, 4, 2]):
    assert genome.shape[0] == sum(layer_dimensions)
    # NOTE: Testing without biases for the moment
    # pos = 0  # FIXME: to be used to fix position over multiples layers
    parameters = []
    for i, (layer_in, layer_out) in enumerate(zip(layer_dimensions[:-1], layer_dimensions[1:])):
        # FIXME: not complete, accumulate offset !!!
        src_idx = jnp.arange(start=0, stop=layer_in, step=d)  # indexes of the previous layer neurons
        target_idx = layer_in + jnp.arange(start=0, stop=layer_out, step=d)  # indexes of the current layer neurons

        weight_matrix = jitted_L2_dist(genome, src_idx, target_idx, d)
        parameters.append(
            {'w': weight_matrix}
        )

    return parameters


res = genome_to_param(
    jnp.arange(10, 26),
)
for r in res:
    print(r['w'])

# [
#     [jnp.sqrt((20 - 24) ** 2), jnp.sqrt((20 - 25) ** 2)],
#     [jnp.sqrt((21 - 24) ** 2), jnp.sqrt((21 - 25) ** 2)],
#     [jnp.sqrt((22 - 24) ** 2), jnp.sqrt((22 - 25) ** 2)],
#     [jnp.sqrt((23 - 24) ** 2), jnp.sqrt((23 - 25) ** 2)],
# ]

# raise ValueError('Not tested!!')
