# Model report -- who forecasts each city best

Median miss (degrees F) between each model's night-before
forecast and the officially settled number, per city; the
signed lean in brackets (+ runs hot, - runs cold). `pool` is
the calibrated GFS+ECMWF median the money actually used;
`gfs`/`ecmwf` are its two voters graded separately (also
calibrated); `icon`/`nws` are raw research passengers riding
along -- a passenger that ties the calibrated incumbents is
doing well. Small n means luck still speaks louder than
skill. RESEARCH ONLY: no trading or calibration code reads
this file, and promotion of any model into the vote is an
owner decision. Regenerated in full by model_report.py.

| city | pool | ecmwf | gfs | hrrr | icon | nws |
|---|---|---|---|---|---|---|
| Atlanta | 1.5 (-0.4) n=22 | 1.9 (+1.2) n=7 | 3.6 (+3.3) n=7 | 3.0 (+3.0) n=1 | 0.7 (-0.7) n=7 | 2.5 (+2.5) n=7 |
| Austin | 1.4 (-0.8) n=21 | 1.2 (-1.0) n=8 | 1.9 (-0.8) n=8 | 3.4 (-3.4) n=1 | 2.8 (-2.8) n=8 | 1.5 (-1.5) n=8 |
| Boston | 2.2 (-2.0) n=15 | 1.8 (-1.3) n=7 | 2.0 (+1.2) n=7 | 0.1 (-0.1) n=1 | 1.3 (-1.3) n=7 | 1.5 (-0.5) n=7 |
| Chicago | 1.6 (-0.5) n=20 | 2.2 (-0.5) n=8 | 1.6 (+0.2) n=8 | 0.7 (-0.7) n=1 | 1.6 (-0.4) n=8 | 2.5 (-2.0) n=8 |
| Dallas | 1.4 (-0.2) n=20 | 1.9 (-1.9) n=8 | 0.8 (-0.0) n=8 | 2.5 (-2.5) n=1 | 1.1 (-0.6) n=8 | 1.0 (-0.5) n=8 |
| Denver | 1.8 (-1.2) n=19 | 1.6 (+1.6) n=7 | 0.9 (-0.5) n=7 | 5.3 (+5.3) n=1 | 1.5 (-1.5) n=7 | 1.5 (-0.5) n=7 |
| Houston | 1.4 (-0.4) n=19 | 3.0 (-3.0) n=7 | 2.2 (+2.2) n=7 | 0.6 (+0.6) n=1 | 1.3 (-1.3) n=7 | 1.5 (+0.5) n=7 |
| Las Vegas | 1.5 (-0.4) n=20 | 1.1 (+1.0) n=7 | 1.0 (-0.9) n=7 | - | 2.5 (-2.5) n=7 | 0.5 (+0.5) n=7 |
| Los Angeles | 3.1 (+2.8) n=14 | 3.1 (+2.8) n=4 | 4.7 (-4.7) n=4 | - | 1.1 (-0.7) n=4 | 1.5 (+1.5) n=4 |
| Miami | 2.0 (-1.5) n=23 | 1.5 (-1.1) n=8 | 2.4 (+1.0) n=8 | 2.3 (-2.3) n=1 | 2.9 (-2.9) n=8 | 1.5 (-0.5) n=8 |
| Minneapolis | 1.6 (-0.6) n=16 | 1.5 (-1.5) n=7 | 4.4 (+4.4) n=7 | 3.2 (-3.2) n=1 | 3.0 (-3.0) n=7 | 0.5 (+0.5) n=7 |
| New Orleans | 1.6 (-0.5) n=19 | 0.8 (-0.7) n=7 | 2.7 (+2.7) n=7 | 1.7 (+1.7) n=1 | 2.3 (-2.3) n=7 | 0.5 (+0.5) n=7 |
| New York City | 2.4 (-1.5) n=15 | 2.8 (-2.8) n=5 | 2.3 (-1.0) n=5 | 0.3 (-0.3) n=1 | 0.3 (+0.0) n=5 | 1.5 (+0.5) n=5 |
| Oklahoma City | 1.5 (-1.0) n=16 | 1.4 (-0.9) n=6 | 1.3 (+1.2) n=6 | 3.5 (-3.5) n=1 | 0.8 (-0.5) n=6 | 1.5 (-1.5) n=6 |
| Philadelphia | 1.4 (-0.9) n=21 | 2.5 (-1.5) n=8 | 1.6 (-1.4) n=8 | 5.6 (-5.6) n=1 | 2.4 (-2.4) n=8 | 2.0 (-2.0) n=8 |
| Phoenix | 1.3 (-1.0) n=18 | 0.9 (-0.6) n=7 | 0.9 (-0.9) n=7 | - | 3.3 (-3.3) n=7 | 1.5 (+0.5) n=7 |
| San Antonio | 1.0 (-0.5) n=21 | 0.9 (-0.5) n=8 | 1.3 (-0.7) n=8 | 1.7 (-1.7) n=1 | 1.8 (-0.9) n=8 | 0.5 (-0.5) n=8 |
| San Francisco | 4.0 (+1.9) n=16 | 4.3 (-4.3) n=5 | 1.7 (+1.0) n=5 | - | 4.6 (-4.6) n=5 | 2.5 (-2.5) n=5 |
| Seattle | 2.5 (-0.9) n=18 | 2.8 (-2.1) n=6 | 3.5 (+3.5) n=6 | - | 2.6 (-2.6) n=6 | 1.5 (+0.0) n=6 |
| Washington DC | 1.5 (+0.7) n=19 | 1.6 (+0.5) n=7 | 1.8 (+0.6) n=7 | - | 3.2 (-3.2) n=7 | 0.5 (-0.5) n=7 |

## Overall (all cities pooled)

- **nws**: median miss 1.50F, lean -0.50F, n=137
- **pool**: median miss 1.60F, lean -0.70F, n=372
- **ecmwf**: median miss 1.80F, lean -1.00F, n=137
- **icon**: median miss 1.90F, lean -1.70F, n=137
- **gfs**: median miss 2.10F, lean +0.20F, n=137
- **hrrr**: median miss 2.40F, lean -1.20F, n=14
