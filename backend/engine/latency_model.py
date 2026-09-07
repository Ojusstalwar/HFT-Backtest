from __future__ import annotations

import numpy as np
from engine.config import LatencyConfig, LatencyPhaseConfig

class LatencyModel:
    """
    Stochastic latency pipeline.
    Samples latencies for different phases from configured distributions.
    """
    def __init__(self, config: LatencyConfig, seed: int | None = None):
        self.config = config
        self.rng = np.random.default_rng(seed)

    @classmethod
    def from_config(cls, config: LatencyConfig) -> LatencyModel:
        return cls(config)

    def _sample(self, phase: LatencyPhaseConfig) -> int:
        dist = phase.distribution
        params = phase.params
        
        while True:
            if dist == "constant":
                val = params.get("value", 0.0)
            elif dist == "lognormal":
                mean = params.get("mean", 0.0)
                sigma = params.get("sigma", 1.0)
                val = self.rng.lognormal(mean=mean, sigma=sigma)
            elif dist == "gamma":
                shape = params.get("shape", 1.0)
                scale = params.get("scale", 1.0)
                val = self.rng.gamma(shape=shape, scale=scale)
            else:
                val = 0.0
                
            val_us = float(val)
            if self.config.bounds_min_us <= val_us <= self.config.bounds_max_us:
                return int(val_us * 1000)
                
            # If bounds fail, loop to resample (simple rejection sampling)

    def sample_feed_latency(self) -> int:
        return self._sample(self.config.feed)

    def sample_processing_latency(self) -> int:
        return self._sample(self.config.processing)

    def sample_order_ingress_latency(self) -> int:
        return self._sample(self.config.order_ingress)

    def sample_ack_egress_latency(self) -> int:
        return self._sample(self.config.ack_egress)

    def apply_latency(self, event: 'Event', phase_name: str) -> 'Event':
        from engine.types import Event
        
        if phase_name == "feed":
            latency = self.sample_feed_latency()
        elif phase_name == "processing":
            latency = self.sample_processing_latency()
        elif phase_name == "order_ingress":
            latency = self.sample_order_ingress_latency()
        elif phase_name == "ack_egress":
            latency = self.sample_ack_egress_latency()
        else:
            latency = 0
            
        # Return a new event with adjusted timestamp
        new_event = Event(
            timestamp_ns=event.timestamp_ns + latency,
            sequence_number=event.sequence_number,
            type_priority=event.type_priority,
            event_type=event.event_type,
            symbol=event.symbol,
            data=event.data.copy()
        )
        return new_event
