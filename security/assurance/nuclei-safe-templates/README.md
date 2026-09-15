# Pocket Lab safe Nuclei templates

This directory is a checked-in allow-list for non-destructive local assurance.
The runtime adapter may execute only templates listed here, against the fixed
Pocket Lab loopback/tunnel target. It must not update templates during a
reproducible run.

The initial contract intentionally contains no exploit, brute-force, active
DoS, credential, or external-network template. Template promotion requires a
reviewed change to this directory and its registry hash.
