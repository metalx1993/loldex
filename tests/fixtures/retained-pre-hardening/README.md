# Retained pre-hardening PHP fixtures

Frozen, unmodified application sources from repository commit `5789e15d367bf8f7c76eb9f9c5ec46ccc1e1bd3f`.
These fixtures exercise the stable security bridge against the actual previous implementation.
They are test-only files and are not part of the public site release.

| File | Git blob | SHA-256 |
| --- | --- | --- |
| `contact.html` | `d77e1ae2453ff29af8a9134df57cba964f3c5107` | `aefda4fe017260c7192d03d408e32794a31d0134ae380ed31dc1bb0f9de639e0` |
| `api.php` | `3d160b16b21fdd69e7b518eef9ee94da54ea5816` | `45c6dd1d47fc3c42148afa02ef20dea00e9c6cdd9679a0ffcd56f5bff72f8e77` |
| `api-v1.php` | `e48c9f4fb00ea21e180f09916871e0ec6cd37767` | `f2f1c695860419d3757252dd0242cab65563ba6a8877532d34d9e2b6169d462d` |
| `api-v1-core.php` | `fa65ea13bbd469aff9932fbf66789ac8ea83d89c` | `0cc8b1ea40206503da34a11e45cca0b5c10268191e39ef09fb53413c9d45f94c` |
| `search-engine.php` | `b76ddab079b14b66228c73051baf5accccd650f0` | `5858ef5d59f140a47e41da16667b4deb2c5f837af9b9d78f4bbce01600862e8f` |

The old contact endpoint in the test is deliberately a synthetic handler that throws if executed.
The bridge must never execute it; no test invokes mail delivery.
