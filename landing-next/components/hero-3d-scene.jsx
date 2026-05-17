"use client";

import { useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Float, Line, OrbitControls, PerspectiveCamera, Sparkles } from "@react-three/drei";
import * as THREE from "three";

function FundCore() {
  const groupRef = useRef(null);
  const shellRef = useRef(null);
  const ringRef = useRef(null);

  useFrame((state) => {
    const t = state.clock.getElapsedTime();
    if (groupRef.current) {
      groupRef.current.rotation.y = t * 0.14;
      groupRef.current.rotation.x = Math.sin(t * 0.3) * 0.08;
    }
    if (shellRef.current) {
      shellRef.current.rotation.x = t * 0.1;
      shellRef.current.rotation.z = t * 0.12;
    }
    if (ringRef.current) {
      ringRef.current.rotation.z = t * 0.22;
      ringRef.current.rotation.y = t * 0.18;
    }
  });

  return (
    <group ref={groupRef}>
      <Float speed={1.2} rotationIntensity={0.25} floatIntensity={0.55}>
        <mesh castShadow receiveShadow>
          <icosahedronGeometry args={[1.05, 2]} />
          <meshStandardMaterial
            color="#8ab4ff"
            emissive="#2658d7"
            emissiveIntensity={0.5}
            roughness={0.2}
            metalness={0.75}
          />
        </mesh>
      </Float>

      <mesh ref={shellRef}>
        <icosahedronGeometry args={[1.45, 1]} />
        <meshStandardMaterial
          color="#8ab4ff"
          wireframe
          transparent
          opacity={0.22}
          emissive="#3b82f6"
          emissiveIntensity={0.15}
        />
      </mesh>

      <mesh ref={ringRef} rotation={[Math.PI / 2.8, 0, 0]}>
        <torusGeometry args={[1.95, 0.045, 24, 120]} />
        <meshStandardMaterial color="#ffb45f" emissive="#9a4f08" emissiveIntensity={0.42} />
      </mesh>
    </group>
  );
}

function SignalLinks() {
  const origin = useMemo(() => new THREE.Vector3(0, 0, 0), []);
  const points = useMemo(() => {
    const radius = 2.35;
    return Array.from({ length: 7 }, (_, i) => {
      const theta = (i / 7) * Math.PI * 2;
      return new THREE.Vector3(Math.cos(theta) * radius, Math.sin(theta * 1.3) * 0.8, Math.sin(theta) * radius);
    });
  }, []);

  return (
    <group>
      {points.map((point, index) => {
        return (
          <group key={index}>
            <mesh position={point}>
              <sphereGeometry args={[0.075, 18, 18]} />
              <meshStandardMaterial color="#dbeafe" emissive="#3b82f6" emissiveIntensity={0.8} />
            </mesh>
            <Line points={[point, origin]} color="#8ab4ff" lineWidth={1} transparent opacity={0.35} />
          </group>
        );
      })}
    </group>
  );
}

export default function Hero3DScene() {
  return (
    <Canvas dpr={[1, 1.8]} shadows>
      <PerspectiveCamera makeDefault position={[0, 1.2, 5.6]} fov={40} />
      <color attach="background" args={["#030507"]} />
      <ambientLight intensity={0.55} />
      <directionalLight position={[3.5, 4.5, 2.2]} intensity={1.35} color="#bfd6ff" />
      <pointLight position={[-2.2, -1.4, 1.8]} intensity={1.4} color="#ffb45f" />
      <Sparkles count={110} size={2.4} scale={[9, 6, 9]} speed={0.28} color="#9ec5ff" />
      <FundCore />
      <SignalLinks />
      <OrbitControls
        enablePan={false}
        enableZoom={false}
        autoRotate
        autoRotateSpeed={0.7}
        minPolarAngle={Math.PI / 2.45}
        maxPolarAngle={Math.PI / 1.95}
      />
    </Canvas>
  );
}