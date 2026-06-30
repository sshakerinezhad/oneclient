import numpy as np

SEED = 42
N_COMPANIES = 100      # background companies (fixtures add a handful more)
N_PERSONS = 500

# Per-region P(company with CB also has Wealth). Quebec deliberately highest -> Q3 winner.
PENETRATION = {
    "Quebec": 0.70, "Ontario": 0.45, "US Northeast": 0.40, "US West": 0.35,
    "US South": 0.30, "Prairies": 0.28, "BC": 0.25, "Atlantic": 0.20, "US Midwest": 0.18,
}

def rng() -> np.random.Generator:
    return np.random.default_rng(SEED)
