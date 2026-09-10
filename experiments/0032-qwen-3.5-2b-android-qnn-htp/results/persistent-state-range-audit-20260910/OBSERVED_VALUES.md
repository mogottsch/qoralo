# Saved p0/p1 returned-state coverage

Counts are values whose **offline next-input QDQ** unbounded code is outside0..65535 after actual transport mapping. They are not observed QNN clipping counts. p1 values project to a hypothetical next call; they do not replay p1. All five returned-state sets are finite. Zero-filled/older cache slots were not loaded or counted.

| State / layer / kind | Input shape → returned shape / transport | QDQp0 | QNNp0 | QDQp1 same pack | QNNp1 same pack | QNNp1 own state |
|---|---|---:|---:|---:|---:|---:|
| 0 / 0 / recurrent | [1, 16, 128, 128] → [1, 16, 128, 128] / clone_replace | 0 | 0 | 0 | 0 | 0 |
| 1 / 1 / recurrent | [1, 16, 128, 128] → [1, 16, 128, 128] / clone_replace | 0 | 0 | 0 | 0 | 0 |
| 2 / 2 / recurrent | [1, 16, 128, 128] → [1, 16, 128, 128] / clone_replace | 0 | 0 | 0 | 0 | 0 |
| 3 / 3 / key_cache_update | [1, 2, 256, 4095] → [1, 2, 256, 1] / write_new_token_at_position_axis_3 | 1 | 1 | 0 | 0 | 0 |
| 4 / 4 / recurrent | [1, 16, 128, 128] → [1, 16, 128, 128] / clone_replace | 0 | 0 | 0 | 0 | 0 |
| 5 / 5 / recurrent | [1, 16, 128, 128] → [1, 16, 128, 128] / clone_replace | 0 | 0 | 0 | 0 | 0 |
| 6 / 6 / recurrent | [1, 16, 128, 128] → [1, 16, 128, 128] / clone_replace | 0 | 0 | 0 | 0 | 0 |
| 7 / 7 / key_cache_update | [1, 2, 256, 4095] → [1, 2, 256, 1] / write_new_token_at_position_axis_3 | 2 | 2 | 0 | 0 | 0 |
| 8 / 8 / recurrent | [1, 16, 128, 128] → [1, 16, 128, 128] / clone_replace | 0 | 0 | 0 | 0 | 0 |
| 9 / 9 / recurrent | [1, 16, 128, 128] → [1, 16, 128, 128] / clone_replace | 0 | 0 | 0 | 0 | 0 |
| 10 / 10 / recurrent | [1, 16, 128, 128] → [1, 16, 128, 128] / clone_replace | 0 | 0 | 0 | 0 | 0 |
| 11 / 11 / key_cache_update | [1, 2, 256, 4095] → [1, 2, 256, 1] / write_new_token_at_position_axis_3 | 1 | 1 | 0 | 0 | 0 |
| 12 / 12 / recurrent | [1, 16, 128, 128] → [1, 16, 128, 128] / clone_replace | 0 | 0 | 0 | 0 | 0 |
| 13 / 13 / recurrent | [1, 16, 128, 128] → [1, 16, 128, 128] / clone_replace | 0 | 0 | 0 | 0 | 0 |
| 14 / 14 / recurrent | [1, 16, 128, 128] → [1, 16, 128, 128] / clone_replace | 0 | 0 | 0 | 0 | 0 |
| 15 / 15 / key_cache_update | [1, 2, 256, 4095] → [1, 2, 256, 1] / write_new_token_at_position_axis_3 | 0 | 0 | 0 | 0 | 0 |
| 16 / 16 / recurrent | [1, 16, 128, 128] → [1, 16, 128, 128] / clone_replace | 0 | 0 | 0 | 0 | 0 |
| 17 / 17 / recurrent | [1, 16, 128, 128] → [1, 16, 128, 128] / clone_replace | 0 | 0 | 0 | 0 | 0 |
| 18 / 18 / recurrent | [1, 16, 128, 128] → [1, 16, 128, 128] / clone_replace | 0 | 0 | 0 | 0 | 0 |
| 19 / 19 / key_cache_update | [1, 2, 256, 4095] → [1, 2, 256, 1] / write_new_token_at_position_axis_3 | 0 | 0 | 0 | 0 | 0 |
| 20 / 20 / recurrent | [1, 16, 128, 128] → [1, 16, 128, 128] / clone_replace | 0 | 0 | 0 | 0 | 0 |
| 21 / 21 / recurrent | [1, 16, 128, 128] → [1, 16, 128, 128] / clone_replace | 0 | 0 | 0 | 0 | 0 |
| 22 / 22 / recurrent | [1, 16, 128, 128] → [1, 16, 128, 128] / clone_replace | 0 | 0 | 0 | 0 | 0 |
| 23 / 23 / key_cache_update | [1, 2, 256, 4095] → [1, 2, 256, 1] / write_new_token_at_position_axis_3 | 0 | 0 | 0 | 0 | 0 |
| 24 / 0 / convolution | [1, 6144, 1, 4] → [1, 6144, 1, 4] / clone_replace | 1 | 1 | 0 | 1 | 1 |
| 25 / 1 / convolution | [1, 6144, 1, 4] → [1, 6144, 1, 4] / clone_replace | 0 | 0 | 0 | 0 | 0 |
| 26 / 2 / convolution | [1, 6144, 1, 4] → [1, 6144, 1, 4] / clone_replace | 1 | 1 | 1 | 1 | 1 |
| 27 / 3 / value_cache_update | [1, 2, 4095, 256] → [1, 2, 1, 256] / write_new_token_at_position_axis_2 | 2 | 2 | 0 | 0 | 0 |
| 28 / 4 / convolution | [1, 6144, 1, 4] → [1, 6144, 1, 4] / clone_replace | 0 | 0 | 0 | 0 | 0 |
| 29 / 5 / convolution | [1, 6144, 1, 4] → [1, 6144, 1, 4] / clone_replace | 0 | 0 | 0 | 0 | 0 |
| 30 / 6 / convolution | [1, 6144, 1, 4] → [1, 6144, 1, 4] / clone_replace | 0 | 0 | 0 | 0 | 0 |
| 31 / 7 / value_cache_update | [1, 2, 4095, 256] → [1, 2, 1, 256] / write_new_token_at_position_axis_2 | 2 | 2 | 0 | 0 | 0 |
| 32 / 8 / convolution | [1, 6144, 1, 4] → [1, 6144, 1, 4] / clone_replace | 0 | 0 | 0 | 0 | 0 |
| 33 / 9 / convolution | [1, 6144, 1, 4] → [1, 6144, 1, 4] / clone_replace | 0 | 0 | 0 | 0 | 0 |
| 34 / 10 / convolution | [1, 6144, 1, 4] → [1, 6144, 1, 4] / clone_replace | 1 | 1 | 0 | 1 | 1 |
| 35 / 11 / value_cache_update | [1, 2, 4095, 256] → [1, 2, 1, 256] / write_new_token_at_position_axis_2 | 0 | 0 | 0 | 0 | 0 |
| 36 / 12 / convolution | [1, 6144, 1, 4] → [1, 6144, 1, 4] / clone_replace | 0 | 0 | 0 | 0 | 0 |
| 37 / 13 / convolution | [1, 6144, 1, 4] → [1, 6144, 1, 4] / clone_replace | 0 | 0 | 0 | 0 | 0 |
| 38 / 14 / convolution | [1, 6144, 1, 4] → [1, 6144, 1, 4] / clone_replace | 0 | 0 | 0 | 0 | 0 |
| 39 / 15 / value_cache_update | [1, 2, 4095, 256] → [1, 2, 1, 256] / write_new_token_at_position_axis_2 | 0 | 0 | 0 | 0 | 0 |
| 40 / 16 / convolution | [1, 6144, 1, 4] → [1, 6144, 1, 4] / clone_replace | 0 | 0 | 0 | 0 | 0 |
| 41 / 17 / convolution | [1, 6144, 1, 4] → [1, 6144, 1, 4] / clone_replace | 0 | 0 | 0 | 0 | 0 |
| 42 / 18 / convolution | [1, 6144, 1, 4] → [1, 6144, 1, 4] / clone_replace | 0 | 0 | 0 | 0 | 0 |
| 43 / 19 / value_cache_update | [1, 2, 4095, 256] → [1, 2, 1, 256] / write_new_token_at_position_axis_2 | 0 | 0 | 0 | 0 | 0 |
| 44 / 20 / convolution | [1, 6144, 1, 4] → [1, 6144, 1, 4] / clone_replace | 0 | 0 | 0 | 0 | 0 |
| 45 / 21 / convolution | [1, 6144, 1, 4] → [1, 6144, 1, 4] / clone_replace | 0 | 0 | 0 | 0 | 0 |
| 46 / 22 / convolution | [1, 6144, 1, 4] → [1, 6144, 1, 4] / clone_replace | 0 | 0 | 0 | 0 | 0 |
| 47 / 23 / value_cache_update | [1, 2, 4095, 256] → [1, 2, 1, 256] / write_new_token_at_position_axis_2 | 0 | 0 | 0 | 0 | 0 |

Complete finite/min/max/zero-bit/tensor hashes, output-domain coverage, next-input rounding and clipping counts, and every clipped example (at most2 per observed state here) with source/destination coordinates are retained in `observations/*.json`. Full range-grid results are in `observations/theory-grid.json`.
