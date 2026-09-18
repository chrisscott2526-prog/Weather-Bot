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
| Atlanta | 1.3 (-0.4) n=24 | 1.5 (+0.1) n=9 | 1.8 (-0.7) n=2 | 3.3 (+2.3) n=9 | 2.5 (+2.5) n=3 | 1.1 (-1.1) n=9 | 0.3 (-0.3) n=2 | 1.5 (+1.5) n=9 | 2.6 (-2.6) n=2 |
| Austin | 1.4 (-0.7) n=23 | 1.2 (-0.8) n=10 | 0.1 (+0.1) n=2 | 1.7 (+0.5) n=10 | 0.9 (-0.9) n=3 | 2.2 (-2.2) n=10 | 0.8 (-0.8) n=2 | 1.5 (-1.0) n=10 | 1.2 (-1.2) n=2 |
| Boston | 2.5 (-2.0) n=17 | 2.5 (-1.3) n=9 | 1.2 (+1.2) n=1 | 2.7 (+1.2) n=9 | 1.2 (+1.2) n=2 | 1.0 (-1.0) n=8 | 1.1 (-1.1) n=1 | 1.5 (+0.0) n=8 | 4.6 (+4.6) n=1 |
| Chicago | 1.6 (-0.6) n=21 | 2.2 (-0.4) n=9 | 4.1 (-4.1) n=1 | 2.1 (-0.2) n=9 | 0.8 (+0.1) n=2 | 1.8 (-0.7) n=9 | 2.4 (-2.4) n=1 | 2.5 (-2.5) n=9 | 0.0 (+0.0) n=1 |
| Dallas | 1.2 (+0.0) n=22 | 1.8 (-0.9) n=10 | 2.3 (-2.3) n=2 | 1.0 (-0.4) n=10 | 0.9 (-0.9) n=3 | 0.8 (-0.4) n=10 | 0.6 (-0.6) n=2 | 1.5 (-0.5) n=9 | 3.5 (-3.5) n=1 |
| Denver | 1.7 (-0.8) n=20 | 1.6 (+1.1) n=8 | 5.7 (-5.7) n=1 | 1.2 (-0.2) n=8 | 3.8 (+3.8) n=2 | 1.5 (-1.5) n=8 | 1.8 (-1.8) n=1 | 1.5 (+0.0) n=8 | 1.5 (+1.5) n=1 |
| Houston | 1.4 (-0.4) n=21 | 3.0 (-2.5) n=9 | 6.0 (+6.0) n=1 | 1.7 (+1.7) n=9 | 1.8 (+1.8) n=2 | 1.4 (-0.8) n=8 | 1.2 (+1.2) n=1 | 1.5 (+0.5) n=8 | 1.3 (-1.3) n=1 |
| Las Vegas | 1.5 (-0.4) n=22 | 1.1 (+0.9) n=9 | - | 0.9 (-0.5) n=9 | 1.5 (-1.5) n=1 | 2.6 (-2.6) n=8 | - | 0.5 (+0.5) n=8 | - |
| Los Angeles | 3.1 (+2.4) n=16 | 3.0 (+0.9) n=6 | 4.3 (-4.3) n=1 | 5.9 (-5.9) n=6 | 7.2 (-7.2) n=2 | 2.4 (-1.1) n=6 | 6.7 (-6.7) n=1 | 1.5 (+0.0) n=6 | 4.6 (-4.6) n=1 |
| Miami | 2.0 (-1.5) n=25 | 1.9 (-1.1) n=10 | 3.9 (+3.9) n=2 | 2.4 (+1.0) n=10 | 2.3 (-2.3) n=3 | 2.9 (-2.9) n=10 | 3.4 (-1.4) n=2 | 1.5 (-0.5) n=10 | 3.4 (-3.4) n=2 |
| Minneapolis | 1.4 (-0.5) n=17 | 1.2 (-1.2) n=8 | - | 4.2 (+3.6) n=8 | 3.2 (-3.2) n=1 | 3.0 (-3.0) n=7 | - | 0.5 (+0.5) n=7 | - |
| New Orleans | 1.6 (-0.5) n=21 | 0.9 (-0.7) n=9 | 0.6 (+0.6) n=1 | 2.6 (+2.6) n=9 | 0.9 (+0.8) n=2 | 1.9 (-1.9) n=8 | 1.7 (-1.7) n=1 | 0.5 (+0.5) n=8 | 1.4 (+1.4) n=1 |
| New York City | 2.3 (-1.5) n=17 | 2.6 (-2.6) n=7 | 3.1 (+1.8) n=2 | 2.3 (-1.0) n=7 | 1.0 (+1.0) n=3 | 0.4 (+0.0) n=7 | 1.1 (+0.6) n=2 | 1.5 (+0.5) n=7 | 2.5 (+0.3) n=2 |
| Oklahoma City | 1.5 (-1.0) n=17 | 1.3 (-0.4) n=7 | 0.1 (+0.1) n=1 | 1.0 (+0.9) n=7 | 2.9 (-2.9) n=2 | 0.5 (+0.0) n=7 | 2.5 (-2.5) n=1 | 1.5 (-1.5) n=7 | 1.9 (-1.9) n=1 |
| Philadelphia | 1.4 (-0.7) n=23 | 2.5 (-0.9) n=10 | 1.4 (+1.4) n=2 | 1.6 (-1.0) n=10 | 2.3 (-2.3) n=3 | 2.2 (-2.2) n=10 | 1.2 (+0.2) n=2 | 2.0 (-1.5) n=10 | 2.0 (+0.5) n=2 |
| Phoenix | 1.3 (-1.2) n=20 | 1.4 (-0.7) n=9 | 13.2 (-13.2) n=1 | 1.0 (-1.0) n=9 | 2.5 (-2.5) n=2 | 4.0 (-4.0) n=9 | 9.2 (-9.2) n=1 | 1.5 (-0.5) n=9 | 5.2 (-5.2) n=1 |
| San Antonio | 1.0 (-0.5) n=23 | 0.8 (-0.5) n=10 | 0.4 (-0.4) n=1 | 1.6 (-0.7) n=10 | 2.1 (-2.1) n=2 | 2.1 (-1.5) n=9 | 1.7 (-1.7) n=1 | 0.5 (-0.5) n=9 | 2.5 (-2.5) n=1 |
| San Francisco | 3.6 (+1.9) n=18 | 3.9 (-1.7) n=7 | 3.2 (-3.2) n=1 | 1.4 (+0.8) n=7 | 3.2 (-3.2) n=2 | 4.0 (-4.0) n=7 | 0.2 (-0.2) n=1 | 1.5 (-1.5) n=7 | 0.9 (-0.9) n=1 |
| Seattle | 2.1 (-0.9) n=20 | 2.5 (-1.2) n=8 | - | 2.9 (+2.2) n=8 | 0.5 (-0.5) n=1 | 3.0 (-3.0) n=7 | - | 1.5 (-0.5) n=7 | - |
| Washington DC | 1.5 (+0.8) n=21 | 1.6 (+0.6) n=9 | 3.4 (+3.4) n=2 | 1.2 (+1.1) n=9 | 3.8 (+3.8) n=2 | 3.0 (-3.0) n=9 | 2.3 (+2.3) n=2 | 0.5 (-0.5) n=9 | 2.2 (+2.2) n=2 |

## Overall (all cities pooled)

- **nbm**: median miss 1.35F, lean -0.80F, n=24
- **nws**: median miss 1.50F, lean -0.50F, n=165
- **pool**: median miss 1.60F, lean -0.60F, n=408
- **ecmwf**: median miss 1.70F, lean -0.50F, n=173
- **gem**: median miss 1.80F, lean +0.15F, n=24
- **gfs**: median miss 1.90F, lean +0.10F, n=173
- **icon**: median miss 1.95F, lean -1.70F, n=166
- **hrrr**: median miss 2.20F, lean -0.70F, n=43
- **ukmo**: median miss 2.20F, lean -1.30F, n=23
