# Known issues

Short list of problems we know about. Each entry: what you see, where it stands, what to do. Not listed here? See [Report a problem](MINING.md#report-a-problem).

## Cooling: start with MeshGraphNet

- **You see:** a Cooling recipe using `prior_krr` is refused at freeze.
- **Status:** `prior_krr` is not available for Cooling until the week-1 update.
- **Workaround:** start Cooling with MeshGraphNet.

## Some catalog entries are practice-only

- **You see:** CNO1d, LSM (deepxde) and, for Burst Thermal, LNO1d and GINO in the catalog.
- **Status:** they run in practice, but have no official GPU receipt yet, so do not count on them for a graded submission.
- **Workaround:** practise with them if you like; choose another tested model type for the graded submission.

## Crowns turn on Challenge by Challenge

- **You see:** a Challenge card that says **Takeovers paused**, or no score to beat.
- **Status:** a crown only goes live on a Challenge once its takeover margin is registered. This happens one Challenge at a time, not all at once.
- **Workaround:** you can still submit and get a grade; the card shows when the crown is live.

## Hidden-exam scores run well below practice

- **You see:** a graded result far lower than your practice total.
- **Status:** expected. Practice uses public cases; the exam is graded on hidden cases your model never sees.
- **Workaround:** aim for a model that generalises, not for the practice number.

## `btcli subnets show` and `btcli subnets metagraph` fail

- **You see:** "storage function SubtensorModule.RootClaimType not found" (btcli 9.21.0 and newer), or "int() argument ... not 'list'" followed by "Subnet 567 does not exist" (9.20.1 and older).
- **Status:** a btcli problem, not Carbon's. It happens on the test network and on mainnet, on every release from 9.8.7 to 9.23.2. We have not found a release that avoids it.
- **Workaround:** none needed for Carbon. Neither command is part of registering or mining. Use bittensor-cli 9.23.2 for registration, and do not read the "does not exist" message as meaning your registration failed.
