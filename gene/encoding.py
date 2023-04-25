import jax.numpy as jnp
from jax import lax
import flax.linen as nn

from gene.network import LinearModel
from gene.distances import Vectorized_distances


def gene_enc_genome_size(config: dict):
    """Computes the effective size of the genome based on the layers dimensionnalities."""
    # The first value in layer_dimension does is only used for the dimensionnality
    # of the input features. So biases are attributed to it
    d = config["encoding"]["d"]
    l_dims = config["net"]["layer_dimensions"]
    return l_dims[0] * d + sum(l_dims[1:]) * (d + 1)


def direct_enc_genome_size(config: dict):
    layer_dims = config["net"]["layer_dimensions"]

    return sum(
        in_f * out_f + out_f for in_f, out_f in zip(layer_dims[:-1], layer_dims[1:])
    )


def gene_decoding(genome: jnp.ndarray, config: dict):
    assert genome.shape[0] == gene_enc_genome_size(config)
    layer_dims = config["net"]["layer_dimensions"]
    d = config["encoding"]["d"]

    # To facilitate acces to the encoding of the weights and the biases (and reduce confusion and possible error in computing indexes), we split the genome in 2 parts
    genome_w, genome_b = jnp.split(genome, [sum(layer_dims) * d])

    model_parameters = {}
    for i, (layer_in, layer_out) in enumerate(zip(layer_dims[:-1], layer_dims[1:])):
        # Split the genome into subarrays, each subarray is the position vector for one neuron
        genome_w_positions = jnp.array(jnp.split(genome_w, sum(layer_dims)))

        layer_offset = sum(layer_dims[:i])
        # indexes of the previous layer neurons
        src_idx = layer_offset + jnp.arange(start=0, stop=layer_in)
        # indexes of the current layer neurons
        target_idx = layer_offset + layer_in + jnp.arange(start=0, stop=layer_out)

        weight_matrix = Vectorized_distances[config["encoding"]["distance"]](
            genome_w_positions, src_idx, target_idx
        )
        # Biases are directly encoded into the genome, they are stored at the end of the genome, in genome_b
        biases = lax.dynamic_slice(
            genome_b, (sum(layer_dims[1 : i + 1]),), (layer_out,)
        )

        model_parameters[f"Dense_{i}"] = {
            "kernel": weight_matrix,
            "bias": biases,
        }

    return model_parameters


def direct_decoding(genome: jnp.ndarray, config: dict):
    """Each weight and bias of the neural network is encoded as a single gene in the genome"""
    layer_dims = config["net"]["layer_dimensions"]

    genome_w, genome_b = jnp.split(
        genome,
        [sum(layer_dims[i] * layer_dims[i + 1] for i in range(len(layer_dims) - 1))],
    )

    model_parameters = {}
    offset = 0
    for i, (layer_in, layer_out) in enumerate(zip(layer_dims[:-1], layer_dims[1:])):
        section_length = layer_in * layer_out
        weights = lax.dynamic_slice(genome_w, (offset,), (section_length,))

        weight_matrix = jnp.reshape(weights, newshape=(layer_in, layer_out))
        biases = lax.dynamic_slice(
            genome_b, (sum(layer_dims[1 : i + 1]),), (layer_out,)
        )

        model_parameters[f"Dense_{i}"] = {
            "kernel": weight_matrix,
            "bias": biases,
        }

        offset += section_length

    return model_parameters


def genome_to_model(genome: jnp.ndarray, config: dict):
    model_parameters = Encoding_function[config["encoding"]["type"]](genome, config)

    model = LinearModel(config["net"]["layer_dimensions"][1:])

    return model, nn.FrozenDict({"params": model_parameters})


Encoding_size_function = {
    "direct": direct_enc_genome_size,
    "gene": gene_enc_genome_size,
}
Encoding_function = {"direct": direct_decoding, "gene": gene_decoding}
