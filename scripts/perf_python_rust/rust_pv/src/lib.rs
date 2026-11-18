//! Benchmark-only transliteration of src/pv_model.py::PVArraySingleDiode.ipv_from_vpv.
//! Does not replace the validated scientific implementation or its protections.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

#[pyclass]
struct PvKernel {
    p: Vec<f64>,
    max_iter: usize,
}

#[pymethods]
impl PvKernel {
    #[new]
    fn new(p: Vec<f64>, max_iter: usize) -> PyResult<Self> {
        if p.len() != 20 || max_iter == 0 || !p.iter().all(|v| v.is_finite()) {
            return Err(PyValueError::new_err(
                "Expected 20 finite PV model parameters and positive max_iter",
            ));
        }
        Ok(Self { p, max_iter })
    }

    fn current(&self, vpv: f64, g: f64, tc: f64) -> f64 {
        let p = &self.p;
        let vmod = vpv / p[0];
        let iph = (g / p[14]) * (p[3] + p[6] * (tc - p[15]));
        let stc_kelvin = p[15] + p[13];
        let vt_stc = p[11] * stc_kelvin / p[10];
        let denom = (p[2] / (p[7] * p[5] * vt_stc)).exp() - 1.0;
        let io_stc = p[3] / denom.max(p[17]);
        let kelvin = tc + p[13];
        let io = io_stc
            * (kelvin / stc_kelvin).powi(3)
            * ((p[12] / (p[7] * p[11])) * (1.0 / stc_kelvin - 1.0 / kelvin)).exp();
        let vt = p[11] * kelvin / p[10];
        let mut current = ((g / p[14]) * p[4]).max(p[16]);
        let a = p[7] * p[5] * vt;
        for _ in 0..self.max_iter {
            let exp_term = ((vmod + current * p[8]) / a.max(p[18])).exp();
            let f = iph - io * (exp_term - 1.0) - (vmod + current * p[8]) / p[9] - current;
            let df = -io * exp_term * (p[8] / a.max(p[18])) - p[8] / p[9] - 1.0;
            let change = -f / df.min(-p[17]);
            let new_current = (current + change).max(p[16]);
            if (new_current - current).abs() < p[19] {
                current = new_current;
                break;
            }
            current = new_current;
        }
        current * p[1]
    }

    fn noop(&self) -> f64 {
        1.0
    }
}

#[pymodule]
fn pv_kernel_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PvKernel>()?;
    Ok(())
}
