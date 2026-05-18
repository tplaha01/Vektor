"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

export default function Hero3DScene() {
  const mountRef = useRef(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color("#030507");

    const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 100);
    camera.position.set(0, 1.2, 5.6);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.8));
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    mount.appendChild(renderer.domElement);

    const ambient = new THREE.AmbientLight("#ffffff", 0.55);
    scene.add(ambient);

    const directional = new THREE.DirectionalLight("#bfd6ff", 1.35);
    directional.position.set(3.5, 4.5, 2.2);
    scene.add(directional);

    const accent = new THREE.PointLight("#ffb45f", 1.4);
    accent.position.set(-2.2, -1.4, 1.8);
    scene.add(accent);

    const starGeo = new THREE.BufferGeometry();
    const starCount = 200;
    const starPositions = new Float32Array(starCount * 3);
    for (let i = 0; i < starCount; i += 1) {
      const i3 = i * 3;
      starPositions[i3] = (Math.random() - 0.5) * 10;
      starPositions[i3 + 1] = (Math.random() - 0.5) * 6;
      starPositions[i3 + 2] = (Math.random() - 0.5) * 10;
    }
    starGeo.setAttribute("position", new THREE.BufferAttribute(starPositions, 3));
    const stars = new THREE.Points(
      starGeo,
      new THREE.PointsMaterial({ color: "#9ec5ff", size: 0.025, transparent: true, opacity: 0.8 })
    );
    scene.add(stars);

    const coreGroup = new THREE.Group();
    scene.add(coreGroup);

    const core = new THREE.Mesh(
      new THREE.IcosahedronGeometry(1.05, 2),
      new THREE.MeshStandardMaterial({
        color: "#8ab4ff",
        emissive: "#2658d7",
        emissiveIntensity: 0.5,
        roughness: 0.2,
        metalness: 0.75,
      })
    );
    coreGroup.add(core);

    const shell = new THREE.Mesh(
      new THREE.IcosahedronGeometry(1.45, 1),
      new THREE.MeshStandardMaterial({
        color: "#8ab4ff",
        wireframe: true,
        transparent: true,
        opacity: 0.22,
        emissive: "#3b82f6",
        emissiveIntensity: 0.15,
      })
    );
    coreGroup.add(shell);

    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(1.95, 0.045, 24, 120),
      new THREE.MeshStandardMaterial({ color: "#ffb45f", emissive: "#9a4f08", emissiveIntensity: 0.42 })
    );
    ring.rotation.set(Math.PI / 2.8, 0, 0);
    coreGroup.add(ring);

    const linksGroup = new THREE.Group();
    scene.add(linksGroup);

    const nodeMaterial = new THREE.MeshStandardMaterial({
      color: "#dbeafe",
      emissive: "#3b82f6",
      emissiveIntensity: 0.8,
    });
    const lineMaterial = new THREE.LineBasicMaterial({ color: "#8ab4ff", transparent: true, opacity: 0.35 });
    const nodeGeo = new THREE.SphereGeometry(0.075, 18, 18);

    const nodes = [];
    const radius = 2.35;
    for (let i = 0; i < 7; i += 1) {
      const theta = (i / 7) * Math.PI * 2;
      const point = new THREE.Vector3(
        Math.cos(theta) * radius,
        Math.sin(theta * 1.3) * 0.8,
        Math.sin(theta) * radius
      );
      const node = new THREE.Mesh(nodeGeo, nodeMaterial);
      node.position.copy(point);
      nodes.push(node);
      linksGroup.add(node);

      const lineGeo = new THREE.BufferGeometry().setFromPoints([point, new THREE.Vector3(0, 0, 0)]);
      const line = new THREE.Line(lineGeo, lineMaterial);
      linksGroup.add(line);
    }

    let frame = 0;
    const start = performance.now();

    const animate = () => {
      frame = requestAnimationFrame(animate);
      const t = (performance.now() - start) / 1000;

      coreGroup.rotation.y = t * 0.14;
      coreGroup.rotation.x = Math.sin(t * 0.3) * 0.08;
      shell.rotation.x = t * 0.1;
      shell.rotation.z = t * 0.12;
      ring.rotation.z = t * 0.22;
      ring.rotation.y = t * 0.18;

      const hover = Math.sin(t * 1.2) * 0.07;
      core.position.y = hover;

      linksGroup.rotation.y = -t * 0.08;
      stars.rotation.y = t * 0.01;

      camera.position.x = Math.sin(t * 0.22) * 0.22;
      camera.position.y = 1.2 + Math.sin(t * 0.32) * 0.08;
      camera.lookAt(0, 0, 0);

      renderer.render(scene, camera);
    };

    const onResize = () => {
      if (!mount) return;
      const width = Math.max(1, mount.clientWidth);
      const height = Math.max(1, mount.clientHeight);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
    };

    onResize();
    window.addEventListener("resize", onResize);
    animate();

    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", onResize);
      if (mount.contains(renderer.domElement)) {
        mount.removeChild(renderer.domElement);
      }
      nodeGeo.dispose();
      nodeMaterial.dispose();
      lineMaterial.dispose();
      starGeo.dispose();
      core.geometry.dispose();
      shell.geometry.dispose();
      ring.geometry.dispose();
      core.material.dispose();
      shell.material.dispose();
      ring.material.dispose();
      renderer.dispose();
    };
  }, []);

  return <div ref={mountRef} style={{ position: "absolute", inset: 0, borderRadius: "inherit" }} />;
}
