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

| city | pool | ecmwf | gem | gfs | hrrr | icon | nbm | nws | ukmo |
|---|---|---|---|---|---|---|---|---|---|
| Atlanta | 1.1 (-0.3) n=25 | 1.4 (+0.0) n=10 | 1.1 (+0.4) n=3 | 2.8 (+2.0) n=10 | 2.4 (+2.4) n=4 | 0.9 (-0.9) n=10 | 0.5 (-0.1) n=3 | 1.5 (+1.5) n=10 | 2.2 (-2.2) n=3 |
| Austin | 1.4 (-0.6) n=24 | 1.1 (-0.5) n=11 | 0.2 (+0.0) n=3 | 1.8 (+1.0) n=11 | 1.2 (-1.2) n=4 | 2.3 (-2.3) n=11 | 1.2 (-1.2) n=3 | 1.5 (-0.5) n=11 | 1.3 (-1.3) n=3 |
| Boston | 2.4 (-2.0) n=18 | 2.1 (-1.2) n=10 | 3.6 (-2.4) n=2 | 2.9 (+0.3) n=10 | 1.5 (-0.1) n=3 | 1.3 (-1.3) n=9 | 4.0 (-4.0) n=2 | 1.5 (-0.5) n=9 | 3.6 (+1.0) n=2 |
| Chicago | 1.5 (-0.5) n=22 | 2.2 (-0.2) n=10 | 4.0 (-4.0) n=2 | 1.6 (-0.1) n=10 | 0.9 (-0.7) n=3 | 1.6 (-0.4) n=10 | 1.6 (-1.6) n=2 | 2.5 (-2.0) n=10 | 0.1 (+0.1) n=2 |
| Dallas | 1.2 (+0.1) n=23 | 1.5 (-0.2) n=11 | 1.8 (-1.8) n=3 | 1.0 (-0.3) n=11 | 1.4 (-1.4) n=4 | 0.6 (-0.2) n=11 | 1.0 (-0.2) n=3 | 1.5 (-0.5) n=10 | 2.3 (-2.3) n=2 |
| Denver | 1.7 (-0.8) n=20 | 1.6 (+1.1) n=8 | 5.7 (-5.7) n=1 | 1.2 (-0.2) n=8 | 3.8 (+3.8) n=2 | 1.5 (-1.5) n=8 | 1.8 (-1.8) n=1 | 1.5 (+0.0) n=8 | 1.5 (+1.5) n=1 |
| Houston | 1.4 (-0.3) n=22 | 2.8 (-2.1) n=10 | 3.6 (+3.6) n=2 | 1.7 (+1.6) n=10 | 2.7 (+2.7) n=3 | 1.6 (-0.2) n=9 | 0.9 (+0.3) n=2 | 1.5 (+0.5) n=9 | 0.9 (-0.4) n=2 |
| Las Vegas | 1.6 (-0.2) n=23 | 1.3 (+1.0) n=10 | 1.6 (-1.6) n=1 | 0.9 (-0.5) n=10 | 0.8 (-0.7) n=2 | 2.7 (-2.7) n=9 | 2.2 (-2.2) n=1 | 0.5 (+0.5) n=9 | 1.0 (-1.0) n=1 |
| Los Angeles | 3.1 (+2.3) n=17 | 3.1 (-0.7) n=7 | 3.5 (-3.5) n=2 | 5.5 (-5.5) n=7 | 5.3 (-5.3) n=3 | 2.7 (-1.2) n=7 | 6.1 (-6.1) n=2 | 1.5 (-1.5) n=7 | 4.7 (-4.7) n=2 |
| Miami | 2.0 (-1.5) n=26 | 1.6 (-1.4) n=11 | 1.3 (+1.3) n=3 | 2.1 (+1.5) n=11 | 1.5 (-1.5) n=4 | 2.8 (-2.8) n=11 | 2.6 (-2.6) n=3 | 1.5 (-0.5) n=11 | 1.7 (-1.7) n=3 |
| Minneapolis | 1.4 (-0.2) n=18 | 1.5 (-1.0) n=9 | 3.0 (-3.0) n=1 | 3.9 (+2.7) n=9 | 2.2 (-1.0) n=2 | 2.6 (-2.6) n=8 | 2.8 (-2.8) n=1 | 1.0 (+0.5) n=8 | 4.2 (+4.2) n=1 |
| New Orleans | 1.6 (-0.1) n=22 | 1.1 (-0.6) n=10 | 0.8 (+0.8) n=2 | 2.5 (+2.5) n=10 | 0.1 (-0.1) n=3 | 1.6 (-1.6) n=9 | 1.2 (-1.2) n=2 | 0.5 (+0.5) n=9 | 1.5 (+1.5) n=2 |
| New York City | 2.2 (-1.4) n=18 | 2.4 (-2.4) n=8 | 1.8 (-1.3) n=3 | 1.6 (-0.7) n=8 | 1.0 (+1.0) n=4 | 0.7 (+0.0) n=8 | 0.6 (+0.2) n=3 | 1.0 (+0.0) n=8 | 2.2 (+0.4) n=3 |
| Oklahoma City | 1.4 (-1.0) n=18 | 1.2 (-0.8) n=8 | 0.3 (-0.2) n=2 | 1.3 (+1.2) n=8 | 2.3 (-2.3) n=3 | 0.4 (+0.0) n=8 | 2.4 (-2.4) n=2 | 1.5 (-1.5) n=8 | 2.7 (-2.7) n=2 |
| Philadelphia | 1.4 (-0.5) n=24 | 2.1 (-0.5) n=11 | 1.8 (+1.1) n=3 | 1.5 (-1.0) n=11 | 3.9 (-3.9) n=4 | 2.3 (-2.3) n=11 | 1.4 (-1.0) n=3 | 2.5 (-1.5) n=11 | 2.5 (-1.5) n=3 |
| Phoenix | 1.3 (-1.2) n=20 | 1.4 (-0.7) n=9 | 13.2 (-13.2) n=1 | 1.0 (-1.0) n=9 | 2.5 (-2.5) n=2 | 4.0 (-4.0) n=9 | 9.2 (-9.2) n=1 | 1.5 (-0.5) n=9 | 5.2 (-5.2) n=1 |
| San Antonio | 1.0 (-0.5) n=23 | 0.8 (-0.5) n=10 | 0.4 (-0.4) n=1 | 1.6 (-0.7) n=10 | 2.1 (-2.1) n=2 | 2.1 (-1.5) n=9 | 1.7 (-1.7) n=1 | 0.5 (-0.5) n=9 | 2.5 (-2.5) n=1 |
| San Francisco | 3.3 (+1.8) n=19 | 3.6 (-1.1) n=8 | 4.6 (-4.6) n=2 | 1.6 (-0.2) n=8 | 2.2 (-2.2) n=3 | 3.9 (-3.9) n=8 | 0.2 (-0.2) n=2 | 1.5 (-1.5) n=8 | 1.0 (-1.0) n=2 |
| Seattle | 1.9 (-0.9) n=21 | 2.3 (-1.5) n=9 | 5.7 (-5.7) n=1 | 2.3 (+2.2) n=9 | 0.6 (+0.1) n=2 | 3.4 (-3.4) n=8 | 3.1 (-3.1) n=1 | 1.5 (-1.0) n=8 | 2.6 (-2.6) n=1 |
| Washington DC | 1.6 (+0.8) n=22 | 1.8 (+0.5) n=10 | 5.3 (+1.5) n=3 | 1.5 (+0.8) n=10 | 3.3 (+3.3) n=3 | 2.4 (-2.4) n=10 | 3.3 (+1.3) n=3 | 1.0 (-0.5) n=10 | 2.6 (+1.8) n=3 |

## Overall (all cities pooled)

- **nbm**: median miss 1.40F, lean -1.00F, n=41
- **nws**: median miss 1.50F, lean -0.50F, n=182
- **pool**: median miss 1.50F, lean -0.50F, n=425
- **ecmwf**: median miss 1.65F, lean -0.50F, n=190
- **icon**: median miss 1.80F, lean -1.70F, n=183
- **gem**: median miss 1.80F, lean -1.30F, n=41
- **gfs**: median miss 1.80F, lean +0.10F, n=190
- **hrrr**: median miss 1.95F, lean -0.70F, n=60
- **ukmo**: median miss 2.20F, lean -1.30F, n=40
