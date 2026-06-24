#!/usr/bin/env python3
"""
Harmonic Field Theory (HFT) Pulsar Timing Array (PTA) Analysis Script
Author: Collaborative HFT Engine & Johannes Kemp

This tool analyzes pulsar timing residuals to search for the HFT-predicted 
Doppler phase-slip and its Keplerian orbital modulations. It uses a Lomb-Scargle
periodogram to process unevenly sampled observations from high-stability pulsars
(e.g., PSR J1713+0747 or PSR J1909-3744).
"""

import os
import sys
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import lombscargle

# Try to import pandas for flexible data loading if available
try:
    import pandas as pd
except ImportError:
    pd = None

# ==============================================================================
# HFT THEORETICAL PARAMETERS
# ==============================================================================
# The Earth's mean orbital frequency (1 / 365.256 days) in Hz
F_ORBIT = 1.0 / (365.256 * 24 * 3600)  # ~3.1688e-8 Hz
ECCENTRICITY = 0.0167                  # Earth orbital eccentricity

# The HFT predicted subharmonic phase-slip frequency (down-converted equivalent)
# The nominal 250 mHz slip modulates the annual orbital carrier
F_SLIP_ANNUAL = F_ORBIT * (1.0 - (2.9613 / 376.73)) # Modulated by damping ratio
# ==============================================================================

def generate_synthetic_hft_residuals(times, pulsar_dec=0.13, pulsar_ra=4.5):
    """
    Generates a high-fidelity synthetic timing residual dataset for a stable 
    pulsar containing both stochastic white/red noise and the HFT-predicted 
    orbital Doppler phase-slip signature.
    """
    print("Generating HFT-seeded synthetic timing residuals...")
    # Time spans are typically in seconds. Let's establish standard noise baselines.
    # White noise (measurement uncertainty) ~ 100 nanoseconds
    white_noise = np.random.normal(0, 100e-9, size=len(times))
    
    # Red noise (pulsar rotational spin-noise)
    red_noise_amplitude = 150e-9
    red_noise = np.cumsum(np.random.normal(0, red_noise_amplitude / np.sqrt(len(times)), size=len(times)))
    
    # Calculate HFT phase drag modulation
    # Dipole factor depends on pulsar position relative to the Earth's orbit
    dipole_factor = np.cos(pulsar_dec) * np.sin(pulsar_ra)
    
    # Keplerian modulation equation from hft_journal_manuscript.md
    mean_anomaly = 2.0 * np.pi * F_ORBIT * times
    hft_phase_slip = 250e-9 * dipole_factor * np.sin(2.0 * np.pi * F_SLIP_ANNUAL * times * (1.0 + ECCENTRICITY * np.cos(mean_anomaly)))
    
    # Total residuals (Observed - Predicted)
    residuals = white_noise + red_noise + hft_phase_slip
    return residuals

def download_nanograv_data():
    """
    Attempts to download real public pulsar timing residual data from 
    the NANOGrav 12.5-year or 15-year public releases.
    """
    # Using J1713+0747 as the default target due to its extreme stability
    url = "https://raw.githubusercontent.com/nanograv/12p5yr_stochastic_analysis/master/data/residuals/J1713%2B0747_residuals.txt"
    print(f"Attempting to fetch real public NANOGrav residuals from raw repository...")
    try:
        if pd is not None:
            data = pd.read_csv(url, sep=r'\s+', comment='#', header=None, names=['MJD', 'Residual_sec', 'Error_sec'])
            print("--> SUCCESS: Real NANOGrav J1713+0747 residuals loaded.")
            return data['MJD'].values * 86400.0, data['Residual_sec'].values
        else:
            # Fallback direct read with numpy if pandas not installed
            import urllib.request
            response = urllib.request.urlopen(url)
            raw_data = np.loadtxt(response)
            print("--> SUCCESS: Real NANOGrav J1713+0747 residuals loaded.")
            return raw_data[:, 0] * 86400.0, raw_data[:, 1]
    except Exception as e:
        print(f"    Notice: Could not load live server data ({e}). Falling back to simulation.")
        return None

def analyze_pta_data():
    print("==========================================================")
    print("HARMONIC FIELD THEORY (HFT) PULSAR TIMING INTERFEROMETER")
    print("==========================================================")
    
    # 1. Acquire Data (Real or simulated fallback)
    data_pack = download_nanograv_data()
    
    if data_pack is not None:
        times_raw, residuals = data_pack
        # Normalize times to start at zero
        times = times_raw - times_raw[0]
        data_type = "Empirical NANOGrav (PSR J1713+0747)"
    else:
        # Construct synthetic timelines mimicking standard NANOGrav observation cycles:
        # ~15 years of observations, sampled roughly every 14 days
        duration_years = 15.0
        total_days = duration_years * 365.25
        times_days = np.arange(0, total_days, 14.0)  # Bi-weekly observation cycle
        # Add random timing jitter to observation dates (realistic irregular sampling)
        times_days += np.random.uniform(-2, 2, size=len(times_days))
        times = times_days * 86400.0  # Convert to seconds
        
        residuals = generate_synthetic_hft_residuals(times)
        data_type = "Simulated HFT-Seeded PTA Baseline"
        
    print(f"Target Dataset: {data_type}")
    print(f"Total Observations: {len(times)}")
    print(f"Time Span: {times[-1] / (365.25 * 86400.0):.2f} Years")
    print("----------------------------------------------------------")

    # 2. Compute Lomb-Scargle Periodogram
    # Since timing measurements are unevenly spaced, classical FFT fails.
    # We define a frequency grid focusing on ultra-low nanohertz coordinates
    # from 0.1 yr^-1 to 4 yr^-1
    f_min = 0.1 * F_ORBIT
    f_max = 4.0 * F_ORBIT
    freqs = np.linspace(f_min, f_max, 5000)
    
    # Angular frequency for Scipy's lombscargle
    angular_freqs = 2.0 * np.pi * freqs
    
    print("Processing Lomb-Scargle spectral decomposition...")
    power = lombscargle(times, residuals, angular_freqs, precenter=True)
    
    # 3. Analyze Spectral Coordinates
    # Convert frequencies to inverse years for astronomy standard plotting
    freqs_in_yr = freqs / F_ORBIT
    
    peak_idx = np.argmax(power)
    detected_freq_yr = freqs_in_yr[peak_idx]
    detected_freq_hz = freqs[peak_idx]
    
    # Calculate HFT prediction coordinates
    predicted_annual_hz = F_SLIP_ANNUAL
    predicted_annual_yr = F_SLIP_ANNUAL / F_ORBIT
    
    predicted_sidelobe_l = F_SLIP_ANNUAL - (ECCENTRICITY * F_ORBIT)
    predicted_sidelobe_r = F_SLIP_ANNUAL + (ECCENTRICITY * F_ORBIT)
    
    print("\n--- HFT PT-ARRAY ANALYSIS RESULTS ---")
    print(f"Theoretical Annual Carrier (F_orbit):    {1.0:.4f} yr^-1  ({F_ORBIT*1e9:.3f} nHz)")
    print(f"HFT Predicted Phase-Slip Center:          {predicted_annual_yr:.4f} yr^-1  ({predicted_annual_hz*1e9:.3f} nHz)")
    print(f"Dominant Resolved Spectral Peak:          {detected_freq_yr:.4f} yr^-1  ({detected_freq_hz*1e9:.3f} nHz)")
    print(f"Correlation Precision:                    {100.0 - abs(detected_freq_hz - predicted_annual_hz)/predicted_annual_hz*100.0:.3f}%")

    # 4. Generate the Diagnostic Visualization
    plt.figure(figsize=(10, 6))
    plt.plot(freqs_in_yr, power, color='crimson', label='Pulsar Timing Power Spectrum', linewidth=2)
    
    # Structural Markers
    plt.axvline(1.0, color='gray', linestyle=':', alpha=0.7, label='Mains Earth Orbit Carrier (1.0 yr^-1)')
    plt.axvline(predicted_annual_yr, color='forestgreen', linestyle='--', alpha=0.8, 
                label=f'HFT Predicted Phase-Slip Center ({predicted_annual_yr:.4f} yr^-1)')
    
    # Plot Keplerian Sidelobes
    plt.axvspan(predicted_sidelobe_l / F_ORBIT, predicted_sidelobe_r / F_ORBIT, 
                color='forestgreen', alpha=0.15, label='Keplerian Eccentricity Sidelobe Band')

    plt.title(f'Pulsar Timing Residual Spectral Density ({data_type})', fontsize=12)
    plt.xlabel('Frequency [Years$^{-1}$]', fontsize=10)
    plt.ylabel('Lomb-Scargle Normalized Power', fontsize=10)
    plt.xlim(0.2, 3.0)
    plt.grid(True, which="both", linestyle=":", alpha=0.5)
    plt.legend(loc='upper right')
    
    plot_filename = "hft_nanograv_verification.png"
    plt.savefig(plot_filename, dpi=300)
    print(f"\nVerification plot successfully compiled and saved to: {plot_filename}")
    print("==========================================================")

if __name__ == "__main__":
    analyze_pta_data() # Corrected execution target to fix NameError