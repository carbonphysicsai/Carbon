"""Carbon Dashboard: a public, read-only display of the validator's score feed.

The dashboard is a reader (DASHBOARD-01, OWNER-DASHBOARD-01). The Carbon
Validator decides what a score is, what is released and who the incumbent is
(VALIDATOR-29). This package checks a signed feed again, keeps only allow-listed
fields, refuses a document that breaks a disclosure rule, and writes the static
site that draws the rest.

DEVELOPMENT / TESTNET display software: no score, rank, frontier, weight,
settlement, qualification or production authority.
"""
