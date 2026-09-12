'use client'

/**
 * LuxuryBackground.tsx
 * Ultra-luxury 3D animated background using Three.js
 * Features: floating particles, wave geometry, gold/cyan glow atmosphere
 */

import { useEffect, useRef } from 'react'
import * as THREE from 'three'

export default function LuxuryBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    // ── Scene setup ──────────────────────────────────────────────
    const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.setSize(window.innerWidth, window.innerHeight)

    const scene  = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 100)
    camera.position.z = 4

    // ── Floating particles (gold + cyan) ─────────────────────────
    const particleCount = 800
    const positions  = new Float32Array(particleCount * 3)
    const colors     = new Float32Array(particleCount * 3)
    const sizes      = new Float32Array(particleCount)

    const goldColor = new THREE.Color('#D4AF37')
    const cyanColor = new THREE.Color('#00D4FF')
    const tealColor = new THREE.Color('#00FFD1')

    for (let i = 0; i < particleCount; i++) {
      positions[i * 3]     = (Math.random() - 0.5) * 20
      positions[i * 3 + 1] = (Math.random() - 0.5) * 12
      positions[i * 3 + 2] = (Math.random() - 0.5) * 8

      // Mix gold and cyan
      const mix  = Math.random()
      const base = mix < 0.5 ? goldColor : (mix < 0.8 ? cyanColor : tealColor)
      colors[i * 3]     = base.r * (0.6 + Math.random() * 0.4)
      colors[i * 3 + 1] = base.g * (0.6 + Math.random() * 0.4)
      colors[i * 3 + 2] = base.b * (0.6 + Math.random() * 0.4)

      sizes[i] = Math.random() * 2.5 + 0.5
    }

    const particleGeo = new THREE.BufferGeometry()
    particleGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    particleGeo.setAttribute('color',    new THREE.BufferAttribute(colors, 3))
    particleGeo.setAttribute('size',     new THREE.BufferAttribute(sizes, 1))

    const particleMat = new THREE.PointsMaterial({
      size:         0.03,
      vertexColors: true,
      transparent:  true,
      opacity:      0.7,
      blending:     THREE.AdditiveBlending,
      sizeAttenuation: true,
    })

    const particles = new THREE.Points(particleGeo, particleMat)
    scene.add(particles)

    // ── Wave geometry (flood wave effect) ────────────────────────
    const waveGeo = new THREE.PlaneGeometry(24, 6, 80, 20)
    const waveMat = new THREE.MeshBasicMaterial({
      color:       0x00D4FF,
      wireframe:   true,
      transparent: true,
      opacity:     0.04,
    })
    const wave = new THREE.Mesh(waveGeo, waveMat)
    wave.rotation.x = -Math.PI / 4
    wave.position.y = -2
    wave.position.z = -2
    scene.add(wave)

    // Second deeper wave
    const wave2Geo = new THREE.PlaneGeometry(24, 8, 60, 15)
    const wave2Mat = new THREE.MeshBasicMaterial({
      color:       0xD4AF37,
      wireframe:   true,
      transparent: true,
      opacity:     0.025,
    })
    const wave2 = new THREE.Mesh(wave2Geo, wave2Mat)
    wave2.rotation.x = -Math.PI / 3.5
    wave2.position.y = -3
    wave2.position.z = -4
    scene.add(wave2)

    // ── Ambient floating orbs ─────────────────────────────────────
    const orbs: THREE.Mesh[] = []
    const orbPositions = [
      [-6, 2, -3], [6, -1, -4], [0, 3, -5],
      [-3, -2, -2], [4, 2, -3], [-5, -3, -5]
    ]

    orbPositions.forEach((pos, i) => {
      const geo = new THREE.SphereGeometry(0.3 + Math.random() * 0.4, 16, 16)
      const mat = new THREE.MeshBasicMaterial({
        color:       i % 2 === 0 ? 0xD4AF37 : 0x00D4FF,
        transparent: true,
        opacity:     0.06 + Math.random() * 0.04,
      })
      const orb = new THREE.Mesh(geo, mat)
      orb.position.set(pos[0], pos[1], pos[2])
      scene.add(orb)
      orbs.push(orb)
    })

    // ── Animation ─────────────────────────────────────────────────
    let animId: number
    const clock = new THREE.Clock()

    const animate = () => {
      animId = requestAnimationFrame(animate)
      const t = clock.getElapsedTime()

      // Rotate particles slowly
      particles.rotation.y = t * 0.015
      particles.rotation.x = Math.sin(t * 0.008) * 0.05

      // Animate wave vertices
      const wavePos = waveGeo.attributes.position as THREE.BufferAttribute
      for (let i = 0; i < wavePos.count; i++) {
        const x = wavePos.getX(i)
        const y = wavePos.getY(i)
        wavePos.setZ(i,
          Math.sin(x * 0.5 + t * 0.8) * 0.15 +
          Math.sin(y * 0.8 + t * 0.6) * 0.1
        )
      }
      wavePos.needsUpdate = true

      const wave2Pos = wave2Geo.attributes.position as THREE.BufferAttribute
      for (let i = 0; i < wave2Pos.count; i++) {
        const x = wave2Pos.getX(i)
        const y = wave2Pos.getY(i)
        wave2Pos.setZ(i,
          Math.sin(x * 0.4 + t * 0.5) * 0.2 +
          Math.cos(y * 0.6 + t * 0.4) * 0.12
        )
      }
      wave2Pos.needsUpdate = true

      // Float orbs
      orbs.forEach((orb, i) => {
        orb.position.y += Math.sin(t * 0.4 + i * 1.2) * 0.002
        orb.position.x += Math.cos(t * 0.3 + i * 0.8) * 0.001
      })

      // Subtle camera drift
      camera.position.x = Math.sin(t * 0.05) * 0.3
      camera.position.y = Math.cos(t * 0.04) * 0.15

      renderer.render(scene, camera)
    }
    animate()

    // ── Resize ────────────────────────────────────────────────────
    const onResize = () => {
      camera.aspect = window.innerWidth / window.innerHeight
      camera.updateProjectionMatrix()
      renderer.setSize(window.innerWidth, window.innerHeight)
    }
    window.addEventListener('resize', onResize)

    // ── Mouse parallax ────────────────────────────────────────────
    const onMouse = (e: MouseEvent) => {
      const mx = (e.clientX / window.innerWidth  - 0.5) * 0.4
      const my = (e.clientY / window.innerHeight - 0.5) * 0.2
      particles.rotation.y = mx * 0.3
      particles.rotation.x = my * 0.15
    }
    window.addEventListener('mousemove', onMouse)

    return () => {
      cancelAnimationFrame(animId)
      window.removeEventListener('resize', onResize)
      window.removeEventListener('mousemove', onMouse)
      renderer.dispose()
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'fixed',
        top: 0, left: 0,
        width: '100%', height: '100%',
        pointerEvents: 'none',
        zIndex: 0,
      }}
    />
  )
}
