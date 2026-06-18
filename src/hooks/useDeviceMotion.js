import { useState, useEffect } from 'react';

export function useDeviceMotion() {
  const [motionEnabled, setMotionEnabled] = useState(false);
  const [tilt, setTilt] = useState({ x: 0, y: 0 });

  useEffect(() => {
    if (!motionEnabled) {
      setTilt({ x: 0, y: 0 });
      return;
    }

    const handleOrientation = (event) => {
      if (event.gamma === null || event.beta === null) return;
      // Soft limits for a premium, constrained float effect
      let x = Math.max(-45, Math.min(45, event.gamma)) / 45;
      let y = Math.max(0, Math.min(90, event.beta));
      y = (y - 45) / 45;
      setTilt({ x, y });
    };

    const handleMouseMove = (e) => {
      // Desktop fallback: track mouse to center of screen
      const x = (e.clientX / window.innerWidth - 0.5) * 2;
      const y = (e.clientY / window.innerHeight - 0.5) * 2;
      setTilt({ x, y });
    };

    window.addEventListener('deviceorientation', handleOrientation);
    window.addEventListener('mousemove', handleMouseMove);

    return () => {
      window.removeEventListener('deviceorientation', handleOrientation);
      window.removeEventListener('mousemove', handleMouseMove);
    };
  }, [motionEnabled]);

  const handleEnableMotion = async () => {
    if (navigator.vibrate) navigator.vibrate(10);
    if (motionEnabled) {
      setMotionEnabled(false);
      return;
    }

    if (typeof DeviceOrientationEvent !== 'undefined' && typeof DeviceOrientationEvent.requestPermission === 'function') {
      try {
        const permission = await DeviceOrientationEvent.requestPermission();
        if (permission === 'granted') setMotionEnabled(true);
      } catch (error) {
        setMotionEnabled(true);
      }
    } else {
      setMotionEnabled(true);
    }
  };

  const getParallaxStyle = (depth) => {
    if (!motionEnabled) return {};
    return {
      transform: `translate(${tilt.x * depth}px, ${tilt.y * depth}px)`,
      // Custom cubic-bezier creates a weighty, liquid physics feel for the cards
      transition: 'transform 0.4s cubic-bezier(0.2, 0.8, 0.2, 1)'
    };
  };

  return { motionEnabled, getParallaxStyle, handleEnableMotion };
}
