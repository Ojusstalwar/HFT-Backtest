# Latency Calibration Guide

Accurate latency modeling is critical for an HFT backtester. This guide explains how to measure, validate, and calibrate the network and processing delays in your simulations.

## 1. How to measure feed latency from broker OMS logs
To get an empirical baseline, you need raw logs from your production broker/OMS:
- **Timestamp 1 (Exchange):** The timestamp stamped by the exchange matching engine.
- **Timestamp 2 (OMS Receipt):** The microsecond/nanosecond timestamp when the packet is ingested by your OMS NIC.
- **Calculation:** `OMS Receipt - Exchange = Feed Latency`.
Perform this over thousands of events across different times of day to generate a latency distribution (percentiles).

## 2. Exchange-published colo specifications
NSE and BSE publish expected network transit times for their colocation facilities (e.g., Tier 1, 2, 3 racks). 
- Use these numbers as a hard lower bound for your latency model.
- Take note of the cable lengths and switch hops specified by the exchange to calculate theoretical minimums (speed of light in fiber).

## 3. PCAP analysis for network latency
If you have access to PCAP (Packet Capture) files from your production environment:
- Use `tcpdump` or Wireshark to measure the time delta between sending an `Order` packet and receiving the `OrderAck`.
- This provides the Round Trip Time (RTT). Half of this RTT is a good proxy for order submission latency.
- Account for TCP/IP or UDP stack overhead in your OS.

## 4. Literature ranges as sanity-check bounds
If you lack proprietary data, use industry standards for your config:
- **Colo (Direct Market Access):** 10-50 microseconds.
- **Leased Line (Proximity Hosting):** 1-5 milliseconds.
- **Retail API (Internet):** 20-150 milliseconds.
Ensure your simulation configurations fall within these bounds based on the architecture you are trying to replicate.

## 5. How to create a calibration config YAML
Create a `latency.yaml` file to feed into the `LatencyModelConfig` object.

```yaml
latency_model:
  type: "lognormal"
  base_latency_ns: 25000         # 25 microseconds
  jitter_std_dev: 5000           # 5 microsecond standard dev
  message_rate_penalty: 100      # Add 100ns per message in queue
  
  # Geographic / Architecture parameters
  architecture: "colo"           # 'colo', 'proximity', 'retail'
  
  # For non-deterministic mode
  random_seed: 42
```

Pass this configuration into your backtester initialization. The `LatencyModel` will automatically apply these distributions to your incoming feed events and outgoing order requests.
