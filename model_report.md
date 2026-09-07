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

| city | pool | ecmwf | gfs | icon | nws |
|---|---|---|---|---|---|
| Atlanta | 1.5 (-0.4) n=18 | 1.9 (+1.9) n=3 | 4.5 (+4.5) n=3 | 0.5 (-0.5) n=3 | 1.5 (+1.5) n=3 |
| Austin | 1.4 (-1.1) n=15 | 2.4 (-2.4) n=2 | 2.7 (-2.7) n=2 | 4.1 (-4.1) n=2 | 2.5 (-2.5) n=2 |
| Boston | 2.5 (-2.5) n=11 | 2.5 (-1.3) n=3 | 1.6 (+1.6) n=3 | 1.3 (-1.3) n=3 | 0.5 (-0.5) n=3 |
| Chicago | 1.4 (-0.9) n=14 | 1.4 (-1.4) n=2 | 1.3 (-0.8) n=2 | 0.4 (-0.4) n=2 | 2.0 (-0.5) n=2 |
| Dallas | 1.5 (-0.9) n=14 | 2.5 (-2.5) n=2 | 1.3 (-1.3) n=2 | 1.2 (-1.2) n=2 | 1.0 (-1.0) n=2 |
| Denver | 2.0 (-1.7) n=14 | 2.3 (-2.3) n=2 | 2.6 (-2.6) n=2 | 5.1 (-5.1) n=2 | 2.0 (-2.0) n=2 |
| Houston | 1.3 (+0.2) n=13 | 3.0 (-3.0) n=1 | 5.4 (+5.4) n=1 | 0.2 (-0.2) n=1 | 0.5 (+0.5) n=1 |
| Las Vegas | 2.2 (-0.8) n=15 | 1.0 (+1.0) n=2 | 0.5 (-0.5) n=2 | 2.8 (-2.8) n=2 | 0.5 (+0.0) n=2 |
| Los Angeles | 3.2 (+3.2) n=11 | 2.9 (+2.9) n=1 | 3.9 (-3.9) n=1 | 0.4 (-0.4) n=1 | 1.5 (-1.5) n=1 |
| Miami | 2.0 (-2.0) n=18 | 3.2 (-3.2) n=3 | 1.1 (-0.9) n=3 | 3.0 (-3.0) n=3 | 1.5 (-1.5) n=3 |
| Minneapolis | 1.6 (-0.6) n=10 | 2.5 (-2.5) n=1 | 2.7 (+2.7) n=1 | 3.5 (-3.5) n=1 | 0.5 (+0.5) n=1 |
| New Orleans | 1.8 (-1.3) n=14 | 2.6 (-2.6) n=2 | 2.4 (+2.4) n=2 | 3.1 (-3.1) n=2 | 1.0 (+1.0) n=2 |
| New York City | 2.5 (-0.9) n=12 | 4.6 (-4.6) n=2 | 2.4 (+1.4) n=2 | 0.8 (+0.5) n=2 | 1.5 (+0.0) n=2 |
| Oklahoma City | 1.8 (-1.2) n=12 | 1.2 (-0.3) n=2 | 2.4 (+2.4) n=2 | 1.0 (-0.5) n=2 | 1.0 (-1.0) n=2 |
| Philadelphia | 1.4 (-0.8) n=16 | 3.1 (-3.1) n=3 | 1.7 (-1.7) n=3 | 4.6 (-4.6) n=3 | 2.5 (-2.5) n=3 |
| Phoenix | 1.3 (-1.3) n=13 | 3.1 (-3.1) n=2 | 1.8 (-1.0) n=2 | 3.9 (-3.9) n=2 | 2.5 (-1.0) n=2 |
| San Antonio | 0.9 (-0.5) n=15 | 1.2 (+0.0) n=2 | 0.7 (-0.7) n=2 | 2.0 (-0.8) n=2 | 0.5 (+0.0) n=2 |
| San Francisco | 4.1 (+2.1) n=13 | 6.7 (-6.7) n=2 | 3.1 (-3.1) n=2 | 5.0 (-5.0) n=2 | 3.5 (-3.5) n=2 |
| Seattle | 2.7 (-0.9) n=13 | 2.3 (-2.3) n=1 | 5.7 (+5.7) n=1 | 2.3 (-2.3) n=1 | 0.5 (+0.5) n=1 |
| Washington DC | 1.5 (-1.2) n=15 | 1.6 (-1.6) n=3 | 0.6 (+0.6) n=3 | 4.7 (-4.7) n=3 | 0.5 (-0.5) n=3 |

## Overall (all cities pooled)

- **nws**: median miss 1.50F, lean -0.50F, n=41
- **pool**: median miss 1.60F, lean -0.80F, n=276
- **gfs**: median miss 2.10F, lean -0.60F, n=41
- **icon**: median miss 2.40F, lean -2.40F, n=41
- **ecmwf**: median miss 2.50F, lean -2.30F, n=41
