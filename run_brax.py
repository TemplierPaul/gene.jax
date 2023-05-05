from jax import jit, vmap, lax, default_backend
import jax.numpy as jnp
import jax.random as jrd
from brax import envs
from brax.envs.wrapper import EpisodeWrapper
import evosax

from functools import partial

from gene.encoding import genome_to_model, gene_enc_genome_size
from gene.tracker import Tracker


def rollout(
    config: dict, model=None, model_parameters=None, env=None, rng_reset=None
) -> float:
    state = jit(env.reset)(rng_reset)

    def rollout_loop(carry, x):
        env_state, cum_reward = carry
        actions = model.apply(model_parameters, env_state.obs)
        new_state = jit(env.step)(env_state, actions)

        corrected_reward = new_state.reward * (1 - new_state.done)
        new_carry = new_state, cum_reward + corrected_reward
        return new_carry, corrected_reward

    carry, _ = lax.scan(
        f=rollout_loop,
        init=(state, state.reward),
        xs=None,
        length=config["problem"]["episode_length"],
    )
    # chex.assert_trees_all_close(carry[-1], jnp.cumsum(returns)[-1])

    return carry[-1]


def evaluate_individual(
    genome: jnp.array,
    rng: jrd.KeyArray,
    config: dict,
    env,
) -> float:
    model, model_parameters = genome_to_model(genome, config=config)

    fitness = rollout(
        model=model,
        model_parameters=model_parameters,
        config=config,
        env=env,
        rng_reset=rng,
    )
    return fitness


def run(config: dict, wdb_run, rng: jrd.KeyArray = jrd.PRNGKey(5)):
    num_dims = gene_enc_genome_size(config)

    rng, rng_init = jrd.split(rng, 2)
    strategy = evosax.Strategies[config["evo"]["strategy_name"]](
        popsize=config["evo"]["population_size"],
        num_dims=num_dims,
    )

    es_params = strategy.default_params.replace(init_min=-2, init_max=2)
    state = strategy.initialize(rng_init, es_params)

    tracker = Tracker(config)
    tracker_state = tracker.init()

    env = envs.get_environment(env_name=config["problem"]["environnment"])
    env = EpisodeWrapper(
        env, episode_length=config["problem"]["episode_length"], action_repeat=1
    )
    vmap_evaluate_individual = vmap(
        partial(evaluate_individual, config=config, env=env), in_axes=(0, None)
    )
    jit_vmap_evaluate_individual = jit(vmap_evaluate_individual)

    for _generation in range(config["evo"]["n_generations"]):
        # RNG key creation for downstream usage
        rng, rng_gen, rng_eval = jrd.split(rng, 3)
        # NOTE - Ask
        x, state = strategy.ask(rng_gen, state, es_params)
        # NOTE - Evaluate
        temp_fitness = jit_vmap_evaluate_individual(x, rng_eval)
        fitness = -1 * temp_fitness

        # NOTE - Tell: overwrites current strategy state with the new updated one
        state = strategy.tell(x, fitness, state, es_params)

        # NOTE - Track metric
        tracker_state = tracker.update(tracker_state, None, temp_fitness)
        tracker.wandb_log(tracker_state, wdb_run)

    return state


config = {
    # "evo": {"strategy_name": "xNES", "n_generations": 1000, "population_size": 200},
    "evo": {
        "strategy_name": "Sep_CMA_ES",
        "n_generations": 1000,
        "population_size": 200,
    },
    "net": {"layer_dimensions": [17, 256, 256, 6]},
    "encoding": {"d": 3, "distance": "pL2", "type": "gene"},
    "problem": {
        "environnment": "halfcheetah",
        "maximize": True,
        "episode_length": 1000,
    },
}

if __name__ == "__main__":
    assert default_backend() == "gpu"

    import wandb

    wdb_run = wandb.init(project="Brax v2 v2", config=config)

    run(config, wdb_run)
