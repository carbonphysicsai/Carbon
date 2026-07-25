"""BaseNeuron for Carbon.

Common functionality for both miners and validators.
Extracted following the official Bittensor subnet template pattern.
"""

import argparse
import bittensor as bt


class BaseNeuron:
    """
    Base class that handles common setup for Carbon neurons.
    """

    neuron_type: str = "BaseNeuron"

    @classmethod
    def add_args(cls, parser: argparse.ArgumentParser):
        parser.add_argument("--netuid", type=int, default=107, help="Subnet netuid")
        parser.add_argument("--neuron.epoch_length", type=int, default=100, help="Blocks per epoch")
        parser.add_argument("--neuron.device", type=str, default="cpu")
        parser.add_argument("--blacklist.force_validator_permit", action="store_true", default=False)
        parser.add_argument("--blacklist.allow_non_registered", action="store_true", default=True)

    def __init__(self, config=None):
        self.config = config or bt.config()
        self.wallet = bt.wallet(config=self.config)
        self.subtensor = bt.subtensor(config=self.config)
        self.metagraph = self.subtensor.metagraph(self.config.netuid)
        self.uid = self.metagraph.hotkeys.index(self.wallet.hotkey.ss58_address)
        self.step = 0

    def sync(self):
        """Sync metagraph with chain."""
        self.metagraph.sync(subtensor=self.subtensor)
