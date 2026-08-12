"""BaseValidatorNeuron for Hydrogen.

Follows the structure from the official Bittensor subnet template.
"""

import time
import threading
import argparse
import bittensor as bt

from hydrogen.base.neuron import BaseNeuron


class BaseValidatorNeuron(BaseNeuron):
    """
    Base class for Hydrogen validators.
    Handles common setup, dendrite, scoring loop, etc.
    """

    neuron_type: str = "ValidatorNeuron"

    @classmethod
    def add_args(cls, parser: argparse.ArgumentParser):
        super().add_args(parser)
        parser.add_argument("--neuron.num_concurrent_forwards", type=int, default=1)
        parser.add_argument("--neuron.sample_size", type=int, default=10)

    def __init__(self, config=None):
        super().__init__(config=config)

        # Dendrite for querying miners
        self.dendrite = bt.dendrite(wallet=self.wallet)

        self.should_exit = False
        self.is_running = False
        self.thread = None

    def run(self):
        self.sync()

        bt.logging.info(f"Hydrogen Validator started on netuid {self.config.netuid}")

        try:
            while not self.should_exit:
                self.sync()
                time.sleep(10)  # Main validation loop placeholder
        except KeyboardInterrupt:
            bt.logging.success("Validator stopped.")
        except Exception as e:
            bt.logging.error(f"Validator error: {e}")

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

    # To be overridden
    async def forward(self):
        pass
