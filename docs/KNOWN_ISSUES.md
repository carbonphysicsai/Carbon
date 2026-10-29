# Known issues

Short list of problems we know about. Each entry: what you see, where it stands, what to do. Not listed here? See [Report a problem](MINING.md#report-a-problem).

## `btcli subnets show` and `btcli subnets metagraph` fail

- **You see:** "storage function SubtensorModule.RootClaimType not found" (btcli 9.21.0 and newer), or "int() argument ... not 'list'" followed by "Subnet 567 does not exist" (9.20.1 and older).
- **Status:** a btcli problem, not Carbon's. It happens on the test network and on mainnet, on every release from 9.8.7 to 9.23.2. We have not found a release that avoids it.
- **Workaround:** none needed for Carbon. Neither command is part of registering or mining. Use bittensor-cli 9.23.2 for registration, and do not read the "does not exist" message as meaning your registration failed.
