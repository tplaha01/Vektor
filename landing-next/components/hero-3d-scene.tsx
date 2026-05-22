'use client';

import { useEffect, useRef } from 'react';
import * as THREE from 'three';

export function Hero3DScene() {
  const containerRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const frameRef = useRef<number>(0);
  const startTimeRef = useRef<number>(0);

  useEffect(() => {
    if (!containerRef.current) return;

    // Setup scene
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0e27);
    sceneRef.current = scene;

    // Setup camera
    const camera = new THREE.PerspectiveCamera(
      50,
      containerRef.current.clientWidth / containerRef.current.clientHeight,
      0.1,
      1000
    );
    camera.position.set(0, 0, 8);
    cameraRef.current = camera;

    // Setup renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(containerRef.current.clientWidth, containerRef.current.clientHeight);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    containerRef.current.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
    scene.add(ambientLight);

    const pointLight = new THREE.PointLight(0x00d4ff, 2);
    pointLight.position.set(10, 10, 10);
    scene.add(pointLight);

    const accentLight = new THREE.PointLight(0xff00ff, 0.8);
    accentLight.position.set(-10, -10, 5);
    scene.add(accentLight);

    // Create central orb
    const orbGeometry = new THREE.IcosahedronGeometry(1.5, 4);
    const orbMaterial = new THREE.MeshStandardMaterial({
      color: 0x00d4ff,
      emissive: 0x0099ff,
      emissiveIntensity: 0.4,
      metalness: 0.8,
      roughness: 0.2,
    });
    const orb = new THREE.Mesh(orbGeometry, orbMaterial);
    scene.add(orb);

    // Create rotating rings
    const ring1Geometry = new THREE.TorusGeometry(2.5, 0.05, 16, 100);
    const ringMaterial = new THREE.MeshStandardMaterial({
      color: 0x00ff88,
      emissive: 0x00ff88,
      emissiveIntensity: 0.3,
      metalness: 0.6,
      roughness: 0.4,
    });
    const ring1 = new THREE.Mesh(ring1Geometry, ringMaterial);
    ring1.rotation.x = Math.PI * 0.3;
    scene.add(ring1);

    const ring2Geometry = new THREE.TorusGeometry(3, 0.04, 16, 100);
    const ring2Material = new THREE.MeshStandardMaterial({
      color: 0xff00ff,
      emissive: 0xff00ff,
      emissiveIntensity: 0.2,
      metalness: 0.6,
      roughness: 0.4,
    });
    const ring2 = new THREE.Mesh(ring2Geometry, ring2Material);
    ring2.rotation.z = Math.PI * 0.4;
    scene.add(ring2);

    // Create particles
    const particlesGeometry = new THREE.BufferGeometry();
    const particleCount = 300;
    const positions = new Float32Array(particleCount * 3);
    for (let i = 0; i < particleCount; i++) {
      positions[i * 3] = (Math.random() - 0.5) * 20;
      positions[i * 3 + 1] = (Math.random() - 0.5) * 20;
      positions[i * 3 + 2] = (Math.random() - 0.5) * 20;
    }
    particlesGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    const particlesMaterial = new THREE.PointsMaterial({
      color: 0x00d4ff,
      size: 0.1,
      transparent: true,
      opacity: 0.5,
    });
    const particles = new THREE.Points(particlesGeometry, particlesMaterial);
    scene.add(particles);

    startTimeRef.current = Date.now();

    // Animation loop
    const animate = () => {
      frameRef.current = requestAnimationFrame(animate);
      const elapsed = (Date.now() - startTimeRef.current) / 1000;

      // Rotate orb
      orb.rotation.x += 0.001;
      orb.rotation.y += 0.002;

      // Rotate rings
      ring1.rotation.x += 0.003;
      ring1.rotation.z -= 0.002;
      ring2.rotation.y += 0.002;
      ring2.rotation.z += 0.0015;

      // Float particles
      particles.rotation.x += 0.0001;
      particles.rotation.y += 0.0002;

      // Gentle camera orbit
      camera.position.x = Math.sin(elapsed * 0.3) * 2;
      camera.position.z = 8 + Math.cos(elapsed * 0.2) * 0.5;
      camera.lookAt(orb.position);

      renderer.render(scene, camera);
    };

    animate();

    // Handle window resize
    const handleResize = () => {
      if (!containerRef.current) return;
      const width = containerRef.current.clientWidth;
      const height = containerRef.current.clientHeight;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
    };

    window.addEventListener('resize', handleResize);

    // Cleanup
    return () => {
      window.removeEventListener('resize', handleResize);
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
      if (containerRef.current && renderer.domElement.parentNode === containerRef.current) {
        containerRef.current.removeChild(renderer.domElement);
      }
      orbGeometry.dispose();
      ring1Geometry.dispose();
      ring2Geometry.dispose();
      particlesGeometry.dispose();
      ringMaterial.dispose();
      ring2Material.dispose();
      orbMaterial.dispose();
      particlesMaterial.dispose();
      renderer.dispose();
    };
  }, []);

  return <div ref={containerRef} style={{ width: '100%', height: '100%', position: 'absolute', inset: 0 }} />;
}
