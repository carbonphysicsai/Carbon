"""BaseMinerNeuron for Carbon.

Follows the structure from the official Bittensor subnet template.
"""

import time
import threading
import argparse
import bittensor as bt

from carbon.base.neuron import BaseNeuron


class BaseMinerNeuron(BaseNeuron):
    """
    Base class for Carbon miners.
    Handles axon setup, blacklisting, priority, and the main run loop.
    """

    neuron_type: str = "MinerNeuron"

    @classmethod
    def add_args(cls, parser: argparse.ArgumentParser):
        super().add_args(parser)
        # Add miner-specific args here if needed

    def __init__(self, config=None):
        super().__init__(config=config)

        if not self.config.blacklist.force_validator_permit:
            bt.logging.warning("Allowing non-validators to send requests. This can be a security risk.")

        # Create and attach axon
        self.axon = bt.axon(
            wallet=self.wallet,
            config=self.config() if callable(self.config) else self.config,
        )

        bt.logging.info("Attaching forward, blacklist, and priority functions to axon.")
        self.axon.attach(
            forward_fn=self.forward,
            blacklist_fn=self.blacklist,
            priority_fn=self.priority,
        )

        self.should_exit = False
        self.is_running = False
        self.thread = None

    def run(self):
        self.sync()
        self.axon.serve(netuid=self.config.netuid, subtensor=self.subtensor)
        self.axon.start()

        bt.logging.info(f"Carbon Miner axon started on netuid {self.config.netuid}")

        try:
            while not self.should_exit:
                time.sleep(5)
                self.sync()
        except KeyboardInterrupt:
            self.axon.stop()
            bt.logging.success("Miner stopped by user.")
        except Exception as e:
            bt.logging.error(f"Miner error: {e}")

    def run_in_background_thread(self):
        if not self.is_running:
            self.should_exit = False
            self.thread = threading.Thread(target=self.run, daemon=True)
            self.thread.start()
            self.is_running = True

    def stop_run_thread(self):
        if self.is_running:
            self.should_exit = True
            if self.thread:
                self.thread.join(5)
            self.is_running = False

    def __enter__(self):
        self.run_in_background_thread()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop_run_thread()

    # These should be overridden in the actual Miner class
    async def forward(self, synapse):
        raise NotImplementedError

    async def blacklist(self, synapse):
        return False, ""

    async def priority(self, synapse):
        return 0.0
