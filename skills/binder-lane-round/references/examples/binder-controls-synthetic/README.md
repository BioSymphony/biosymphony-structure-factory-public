# Synthetic Binder Controls

This fixture checks the public control-index and calibration algorithms without a predictor, provider, sequence, or structure file.

The panel declares three required positive controls, three required negative controls, two optional controls, two predictors, and one seed. The observation rows omit the optional controls. `derive_calibration` therefore returns `ready_with_optional_gaps`: the required 3-by-3 panel separates on the selected metric, and the readiness record names the optional rows that a later run can add.

The metric values are constructed examples. The derived thresholds check arithmetic and record shape only; they do not estimate binding or predictor accuracy.
