**Carbon submission terms, version v1**

**1. What this covers.** These terms apply to every submission you deliberately send through Carbon's submission process (the recipe, files, code, configuration and model state named in the submission's manifest and receipt). They apply from the moment your submission is recorded with terms version v1. They do not apply to anything you did not submit.

**2. Carbon's rights.** When you submit, you give Carbon full rights to your submission: Carbon may use, copy, run, inspect, change, combine, train from, build on, publish results of, sell, and license to others your submission and anything made from it. This applies in every country, for as long as the rights exist, without payment to you beyond the rewards set out in the network's reward rules. You cannot take these rights back. They apply whether or not your submission scores well, wins or is ever used.

**3. Models Carbon builds.** Any model Carbon builds or trains from your submission belongs to Carbon.

**4. Your promises.** You may only submit work you have the right to give these rights to. Do not submit anyone else's code, data, weights or secrets unless their licence allows this use. Name any third-party component and its licence in your submission. Those components stay under their own licences.

**5. Client deals.** If Carbon agrees different terms with a specific client, those terms govern that client's work. Nothing in a client deal reduces Carbon's rights in your submission unless Carbon says so in writing.

**6. Grading is separate.** These rights do not mean Carbon has validated, scored or approved your work, and they do not promise you any reward. Scores and rewards follow the published exam and reward rules only.

**7. Only new submissions.** These terms apply only to submissions recorded under this version or a later one that you accept. Earlier submissions keep the terms (if any) they were made under.

**8. Changes.** Carbon may publish a new version. A new version applies only to submissions you make after it is shown to you and recorded with your submission. It never changes an earlier submission's terms.

**9. Official submission burn and infrastructure retry credits.** Where a Challenge version registers an on-chain submission burn requirement, each admitted official submission requires either (a) one unspent finalized buy-and-burn transaction (`SubtensorModule.add_stake_burn`) on the Challenge's Bittensor subnet meeting that version's published TAO amount and Challenge, validator-receiver and hotkey binding, executed directly on-chain from your wallet, or (b) one unspent infrastructure retry credit issued on that validator host. Carbon never receives, holds or refunds TAO or Alpha. An on-chain burn is non-refundable once executed on the blockchain; if a submission is refused at the door before admission to build, its unspent burn transaction remains eligible for a later submission on the same Challenge, validator receiver and hotkey within the validator's lookback window. Once a submission is admitted to build, its burn or retry credit is spent whether the candidate scores, is graded a duplicate (`DUPLICATE`), is withdrawn by the miner (`WITHDRAWN_BY_MINER`), fails a gate, hits a resource limit or fails to build on its own code. If an admitted submission ends in a proven validator-side infrastructure failure after automatic retries (`FAILED_INFRA`) or is closed ungraded when a Challenge version closes (`version_closed`), the validator records one non-cash, non-transferable retry credit for that hotkey on that Challenge, good for one subsequent official submission and carrying no monetary or redemption value. Paying a submission burn never enters any score, gate, ranking or reward calculation.
