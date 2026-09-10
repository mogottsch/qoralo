# Every labelled output — saved-data comparisons

All paired rows have bit-identical native outputs; the last row is the retained single-channel anchor. Full intermediate scalar records and both-channel comparisons are in `analysis.json`. H/C/O flags describe fullchain scalar code clipping, **not observed native stages**. Direct-O is a separate scalar path. Labels can overlap in input bits; they are not39 independent unique values.

| Label | Input FP32 (bits LE) | QNN output FP32 (bits LE) | Fullchain | Direct output | H/C/O clipped | Direct-O clipped | Fullchain ULP distance |
|---|---|---|---:|---:|---|---|---:|
| zero | 0.0 (`00000000`) | 0.0 (`00000000`) | 0.0 | 0.0 | false/false/false | false | 0 |
| negative_zero | -0.0 (`00000080`) | 0.0 (`00000000`) | 0.0 | 0.0 | false/false/false | false | 0 |
| half | 0.5 (`0000003f`) | 0.49958908557891846 (`24caff3e`) | 0.49958905577659607 | 0.5004067420959473 | false/false/false | false | 1 |
| negative_three_quarters | -0.75 (`000040bf`) | -0.7497923970222473 (`65f23fbf`) | -0.7497923970222473 | -0.7497923970222473 | false/false/false | false | 0 |
| one | 1.0 (`0000803f`) | 0.9999958276748657 (`baff7f3f`) | 0.999995768070221 | 0.999995768070221 | false/false/false | false | 1 |
| interior_upper | 20.0 (`0000a041`) | 20.000734329223633 (`8101a041`) | 19.999916076660156 | 19.999916076660156 | false/false/false | false | 429 |
| ordinary_half_step_-100_below | -0.07894309610128403 (`ebaca1bd`) | -0.07931282371282578 (`c36ea2bd`) | -0.07931283116340637 | -0.07931283116340637 | false/false/false | false | 1 |
| ordinary_half_step_-100_at | -0.07894308865070343 (`eaaca1bd`) | -0.07931282371282578 (`c36ea2bd`) | -0.07849517464637756 | -0.07931283116340637 | false/false/false | false | 109743 |
| ordinary_half_step_-100_above | -0.07894308120012283 (`e9aca1bd`) | -0.07931282371282578 (`c36ea2bd`) | -0.07849517464637756 | -0.07931283116340637 | false/false/false | false | 109743 |
| ordinary_half_step_100_below | 0.07973647862672806 (`e14ca33d`) | 0.08013049513101578 (`751ba43d`) | 0.07931283116340637 | 0.08013048768043518 | false/false/false | false | 109745 |
| ordinary_half_step_100_at | 0.07973648607730865 (`e24ca33d`) | 0.08013049513101578 (`751ba43d`) | 0.07931283116340637 | 0.08013048768043518 | false/false/false | false | 109745 |
| ordinary_half_step_100_above | 0.07973649352788925 (`e34ca33d`) | 0.08013049513101578 (`751ba43d`) | 0.08013048768043518 | 0.08013048768043518 | false/false/false | false | 1 |
| history_upper_endpoint_below | 22.131832122802734 (`fe0db141`) | 22.132368087768555 (`170fb141`) | 22.131549835205078 | 22.131549835205078 | false/false/false | false | 429 |
| history_upper_endpoint_at | 22.131834030151367 (`ff0db141`) | 22.132368087768555 (`170fb141`) | 22.131549835205078 | 22.131549835205078 | false/false/false | false | 429 |
| history_upper_endpoint_above | 22.1318359375 (`000eb141`) | 22.132368087768555 (`170fb141`) | 22.131549835205078 | 22.131549835205078 | false/false/false | false | 429 |
| upper_nominal_half_step_below | 22.13222885131836 (`ce0eb141`) | 22.132368087768555 (`170fb141`) | 22.131549835205078 | 22.132368087768555 | false/false/false | false | 429 |
| upper_nominal_half_step_at | 22.132230758666992 (`cf0eb141`) | 22.132368087768555 (`170fb141`) | 22.131549835205078 | 22.132368087768555 | true/false/false | false | 429 |
| upper_nominal_half_step_above | 22.132232666015625 (`d00eb141`) | 22.132368087768555 (`170fb141`) | 22.131549835205078 | 22.132368087768555 | true/false/false | false | 429 |
| upper_actual_clipping_onset_below | 22.13222885131836 (`ce0eb141`) | 22.132368087768555 (`170fb141`) | 22.131549835205078 | 22.132368087768555 | false/false/false | false | 429 |
| upper_actual_clipping_onset_at | 22.132230758666992 (`cf0eb141`) | 22.132368087768555 (`170fb141`) | 22.131549835205078 | 22.132368087768555 | true/false/false | false | 429 |
| upper_actual_clipping_onset_above | 22.132232666015625 (`d00eb141`) | 22.132368087768555 (`170fb141`) | 22.131549835205078 | 22.132368087768555 | true/false/false | false | 429 |
| upper_plus_one_step | 22.132627487182617 (`9f0fb141`) | 22.133188247680664 (`c510b141`) | 22.131549835205078 | 22.132368087768555 | true/false/false | false | 859 |
| upper_plus_two_steps | 22.133420944213867 (`3f11b141`) | 22.134004592895508 (`7112b141`) | 22.131549835205078 | 22.1331844329834 | true/false/false | false | 1287 |
| upper_gap_midpoint | 22.926864624023438 (`386ab741`) | 22.927133560180664 (`c56ab741`) | 22.131549835205078 | 22.92713165283203 | true/false/false | false | 417115 |
| final_upper_below | 23.721893310546875 (`70c6bd41`) | 23.72189712524414 (`72c6bd41`) | 22.131549835205078 | 23.721895217895508 | true/false/false | false | 833800 |
| final_upper_at | 23.721895217895508 (`71c6bd41`) | 23.72189712524414 (`72c6bd41`) | 22.131549835205078 | 23.721895217895508 | true/false/false | false | 833800 |
| history_lower_endpoint_below | -29.86349868774414 (`72e8eec1`) | -29.863319396972656 (`14e8eec1`) | -29.863325119018555 | -29.863325119018555 | false/false/false | false | 3 |
| history_lower_endpoint_at | -29.863496780395508 (`71e8eec1`) | -29.863319396972656 (`14e8eec1`) | -29.863325119018555 | -29.863325119018555 | false/false/false | false | 3 |
| history_lower_endpoint_above | -29.863494873046875 (`70e8eec1`) | -29.863319396972656 (`14e8eec1`) | -29.863325119018555 | -29.863325119018555 | false/false/false | false | 3 |
| lower_nominal_half_step_below | -29.863895416259766 (`42e9eec1`) | -29.863319396972656 (`14e8eec1`) | -29.863325119018555 | -29.863325119018555 | false/false/false | true | 3 |
| lower_nominal_half_step_at | -29.863893508911133 (`41e9eec1`) | -29.863319396972656 (`14e8eec1`) | -29.863325119018555 | -29.863325119018555 | false/false/false | true | 3 |
| lower_nominal_half_step_above | -29.8638916015625 (`40e9eec1`) | -29.863319396972656 (`14e8eec1`) | -29.863325119018555 | -29.863325119018555 | false/false/false | true | 3 |
| lower_actual_clipping_onset_below | -29.86389923095703 (`44e9eec1`) | -29.863319396972656 (`14e8eec1`) | -29.863325119018555 | -29.863325119018555 | true/false/false | true | 3 |
| lower_actual_clipping_onset_at | -29.8638973236084 (`43e9eec1`) | -29.863319396972656 (`14e8eec1`) | -29.863325119018555 | -29.863325119018555 | true/false/false | true | 3 |
| lower_actual_clipping_onset_above | -29.863895416259766 (`42e9eec1`) | -29.863319396972656 (`14e8eec1`) | -29.863325119018555 | -29.863325119018555 | false/false/false | true | 3 |
| lower_minus_one_step | -29.864290237426758 (`11eaeec1`) | -29.863319396972656 (`14e8eec1`) | -29.863325119018555 | -29.863325119018555 | true/false/false | true | 3 |
| lower_minus_two_steps | -29.865083694458008 (`b1ebeec1`) | -29.863319396972656 (`14e8eec1`) | -29.863325119018555 | -29.863325119018555 | true/false/false | true | 3 |
| final_lower_at | -29.863325119018555 (`17e8eec1`) | -29.863319396972656 (`14e8eec1`) | -29.863325119018555 | -29.863325119018555 | false/false/false | false | 3 |
| final_lower_above | -29.863323211669922 (`16e8eec1`) | -29.863319396972656 (`14e8eec1`) | -29.863325119018555 | -29.863325119018555 | false/false/false | false | 3 |
| retained_original_outlier | 23.721895217895508 (`71c6bd41`) | 23.72189712524414 (`72c6bd41`) | 22.131549835205078 | 23.721895217895508 | true/false/false | false | 833800 |
