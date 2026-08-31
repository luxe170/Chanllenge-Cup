import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls as ThreeOrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import type { GraphEdge, GraphNode } from '../../types'

interface Graph3DProps {
  nodes: GraphNode[]
  edges: GraphEdge[]
  hierarchy: GraphNode['type'][]
  selectedNodeId: string
  scale: number
  resetSignal: number
  onSelectNode: (node: GraphNode) => void
}

interface SceneProps extends Graph3DProps {
  labelRefs: React.MutableRefObject<Record<string, HTMLButtonElement | null>>
}

const colors: Record<GraphNode['type'], string> = {
  position: '#8172ff',
  skill: '#4cdbeb',
  cluster: '#5ee0a8',
  stack: '#ffc36f',
}

const nodeRadius: Record<GraphNode['type'], number> = {
  position: .42,
  skill: .31,
  cluster: .49,
  stack: .55,
}

type WorldPosition = [number, number, number]

const createAutoLayout = (nodes: GraphNode[], hierarchy: GraphNode['type'][]) => {
  const presentTypes = new Set(nodes.map((node) => node.type))
  const layerOrder = hierarchy.filter((type) => presentTypes.has(type))
  const positions = new Map<string, WorldPosition>()
  const layerGap = 2.45
  const topY = ((layerOrder.length - 1) * layerGap) / 2

  layerOrder.forEach((type, layerIndex) => {
    const layerNodes = nodes.filter((node) => node.type === type)
    const count = layerNodes.length
    const radiusX = count === 1 ? 0 : Math.min(6.2, 1.8 + count * .48)
    const radiusZ = count === 1 ? 0 : Math.min(3.2, .8 + count * .26)
    const y = topY - layerIndex * layerGap

    layerNodes.forEach((node, index) => {
      if (count === 1) {
        positions.set(node.id, [0, y, 0])
        return
      }
      const angle = (index / count) * Math.PI * 2 - Math.PI / 2
      positions.set(node.id, [Math.cos(angle) * radiusX, y, Math.sin(angle) * radiusZ])
    })
  })

  return positions
}

function CameraControls({ resetSignal }: { resetSignal: number }) {
  const { camera, gl } = useThree()
  const controlsRef = useRef<ThreeOrbitControls | null>(null)

  useEffect(() => {
    const controls = new ThreeOrbitControls(camera, gl.domElement)
    controls.enableDamping = true
    controls.dampingFactor = .075
    controls.enablePan = false
    controls.minDistance = 8
    controls.maxDistance = 22
    controls.minPolarAngle = Math.PI * .2
    controls.maxPolarAngle = Math.PI * .8
    controls.rotateSpeed = .55
    controls.zoomSpeed = .75
    controls.target.set(0, 0, 0)
    controlsRef.current = controls
    return () => controls.dispose()
  }, [camera, gl])

  useEffect(() => {
    camera.position.set(0, .35, 14)
    camera.lookAt(0, 0, 0)
    controlsRef.current?.target.set(0, 0, 0)
    controlsRef.current?.update()
  }, [camera, resetSignal])

  useFrame(() => controlsRef.current?.update())
  return null
}

function StarField() {
  const positions = useMemo(() => {
    const values = new Float32Array(420)
    let seed = 37
    for (let index = 0; index < values.length; index += 3) {
      seed = (seed * 16807) % 2147483647
      values[index] = ((seed % 1000) / 1000 - .5) * 22
      seed = (seed * 16807) % 2147483647
      values[index + 1] = ((seed % 1000) / 1000 - .5) * 14
      seed = (seed * 16807) % 2147483647
      values[index + 2] = -2 - ((seed % 1000) / 1000) * 10
    }
    return values
  }, [])

  return (
    <points>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial color="#5d8cac" size={.025} transparent opacity={.65} sizeAttenuation />
    </points>
  )
}

function NodeMesh({ node, position, selected, highlighted, onSelect }: { node: GraphNode; position: WorldPosition; selected: boolean; highlighted: boolean; onSelect: () => void }) {
  const meshRef = useRef<THREE.Mesh>(null)
  const glowRef = useRef<THREE.Mesh>(null)
  const [hovered, setHovered] = useState(false)
  const radius = nodeRadius[node.type]

  useEffect(() => {
    if (!hovered) return
    document.body.style.cursor = 'pointer'
    return () => { document.body.style.cursor = '' }
  }, [hovered])

  useFrame(({ clock }) => {
    if (!meshRef.current || !glowRef.current) return
    const pulse = selected ? 1.06 + Math.sin(clock.elapsedTime * 2.8) * .035 : hovered ? 1.08 : 1
    meshRef.current.scale.lerp(new THREE.Vector3(pulse, pulse, pulse), .12)
    glowRef.current.rotation.y += .004
  })

  return (
    <group position={position}>
      <mesh
        ref={meshRef}
        onClick={(event) => { event.stopPropagation(); onSelect() }}
        onPointerEnter={(event) => { event.stopPropagation(); setHovered(true) }}
        onPointerLeave={() => setHovered(false)}
      >
        <sphereGeometry args={[radius, 36, 36]} />
        <meshStandardMaterial
          color={colors[node.type]}
          emissive={colors[node.type]}
          emissiveIntensity={selected ? .72 : hovered ? .5 : .25}
          transparent
          opacity={highlighted ? 1 : .42}
          metalness={.14}
          roughness={.3}
        />
      </mesh>
      <mesh ref={glowRef} scale={selected ? 1.45 : 1.28}>
        <sphereGeometry args={[radius, 24, 24]} />
        <meshBasicMaterial color={colors[node.type]} transparent opacity={highlighted ? (selected ? .12 : .055) : .025} side={THREE.BackSide} blending={THREE.AdditiveBlending} />
      </mesh>
      {node.trend === 'new' && (
        <mesh position={[radius * .78, radius * .78, radius * .7]}>
          <sphereGeometry args={[.08, 16, 16]} />
          <meshBasicMaterial color="#72f0b5" toneMapped={false} />
        </mesh>
      )}
    </group>
  )
}

function EdgeLine({ sourcePosition, targetPosition, relationship, highlighted }: { sourcePosition: WorldPosition; targetPosition: WorldPosition; relationship: GraphEdge['relationship']; highlighted: boolean }) {
  const line = useMemo(() => {
    const geometry = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(...sourcePosition),
      new THREE.Vector3(...targetPosition),
    ])
    const material = new THREE.LineBasicMaterial({
      color: relationship === 'BELONGS_TO' ? '#57d8aa' : '#6dbcd8',
      transparent: true,
      opacity: highlighted ? .92 : .12,
      blending: THREE.AdditiveBlending,
    })
    return new THREE.Line(geometry, material)
  }, [highlighted, relationship, sourcePosition, targetPosition])

  useEffect(() => () => {
    line.geometry.dispose()
    if (Array.isArray(line.material)) line.material.forEach((material) => material.dispose())
    else line.material.dispose()
  }, [line])

  return <primitive object={line} />
}

function ProjectLabels({ nodes, positions, highlightedIds, groupRef, labelRefs }: { nodes: GraphNode[]; positions: Map<string, WorldPosition>; highlightedIds: Set<string>; groupRef: React.RefObject<THREE.Group | null>; labelRefs: SceneProps['labelRefs'] }) {
  const vector = useMemo(() => new THREE.Vector3(), [])
  const worldPosition = useMemo(() => new THREE.Vector3(), [])

  useFrame(({ camera, size }) => {
    const group = groupRef.current
    if (!group) return
    group.updateMatrixWorld()
    nodes.forEach((node) => {
      const element = labelRefs.current[node.id]
      if (!element) return
      const position = positions.get(node.id)
      if (!position) return
      worldPosition.set(...position).applyMatrix4(group.matrixWorld)
      vector.copy(worldPosition).project(camera)
      const visible = vector.z > -1 && vector.z < 1
      element.style.opacity = visible ? (highlightedIds.has(node.id) ? '1' : '.46') : '0'
      element.style.transform = `translate(-50%, -50%) translate(${(vector.x * .5 + .5) * size.width}px, ${(-vector.y * .5 + .5) * size.height}px)`
      element.style.zIndex = String(Math.max(1, Math.round((1 - vector.z) * 50)))
    })
  })

  return null
}

function GraphScene({ nodes, edges, hierarchy, selectedNodeId, scale, resetSignal, onSelectNode, labelRefs }: SceneProps) {
  const groupRef = useRef<THREE.Group>(null)
  const nodeMap = useMemo(() => new Map(nodes.map((node) => [node.id, node])), [nodes])
  const positions = useMemo(() => createAutoLayout(nodes, hierarchy), [nodes, hierarchy])
  const highlightedIds = useMemo(() => {
    const ids = new Set<string>([selectedNodeId])
    edges.forEach((edge) => {
      if (edge.source === selectedNodeId) ids.add(edge.target)
      if (edge.target === selectedNodeId) ids.add(edge.source)
    })
    return ids
  }, [edges, selectedNodeId])

  return (
    <>
      <ambientLight intensity={.58} />
      <pointLight position={[5, 7, 8]} intensity={42} color="#b9f7ff" distance={28} />
      <pointLight position={[-7, -3, 5]} intensity={32} color="#7768ff" distance={24} />
      <pointLight position={[0, 0, -3]} intensity={18} color="#44d8ae" distance={18} />
      <StarField />
      <group ref={groupRef} scale={scale}>
        {edges.map((edge, index) => {
          const source = nodeMap.get(edge.source)
          const target = nodeMap.get(edge.target)
          const sourcePosition = positions.get(edge.source)
          const targetPosition = positions.get(edge.target)
          const highlighted = edge.source === selectedNodeId || edge.target === selectedNodeId
          return source && target && sourcePosition && targetPosition ? <EdgeLine key={`${edge.source}-${edge.target}-${index}`} sourcePosition={sourcePosition} targetPosition={targetPosition} relationship={edge.relationship} highlighted={highlighted} /> : null
        })}
        {nodes.map((node) => <NodeMesh key={node.id} node={node} position={positions.get(node.id) ?? [0, 0, 0]} selected={node.id === selectedNodeId} highlighted={highlightedIds.has(node.id)} onSelect={() => onSelectNode(node)} />)}
      </group>
      <ProjectLabels nodes={nodes} positions={positions} highlightedIds={highlightedIds} groupRef={groupRef} labelRefs={labelRefs} />
      <CameraControls resetSignal={resetSignal} />
    </>
  )
}

export default function Graph3D({ nodes, edges, hierarchy, selectedNodeId, scale, resetSignal, onSelectNode }: Graph3DProps) {
  const labelRefs = useRef<Record<string, HTMLButtonElement | null>>({})

  return (
    <div className="graph-3d-root">
      <Canvas
        camera={{ position: [0, .35, 14], fov: 46, near: .1, far: 80 }}
        dpr={[1, 1.75]}
        gl={{ antialias: true, alpha: true, powerPreference: 'high-performance' }}
        onCreated={({ gl }) => {
          gl.outputColorSpace = THREE.SRGBColorSpace
          gl.toneMapping = THREE.ACESFilmicToneMapping
          gl.toneMappingExposure = 1.08
        }}
      >
        <GraphScene
          nodes={nodes}
          edges={edges}
          hierarchy={hierarchy}
          selectedNodeId={selectedNodeId}
          scale={scale}
          resetSignal={resetSignal}
          onSelectNode={onSelectNode}
          labelRefs={labelRefs}
        />
      </Canvas>
      <div className="graph-3d-labels">
        {nodes.map((node) => (
          <button
            key={node.id}
            ref={(element) => { labelRefs.current[node.id] = element }}
            className={`graph-3d-label label-${node.type} ${selectedNodeId === node.id ? 'selected' : ''}`}
            onClick={() => onSelectNode(node)}
          >
            <strong>{node.name.replaceAll('\n', ' ')}</strong>
            {node.weight && <span>{Math.round(node.weight * 100)}%</span>}
          </button>
        ))}
      </div>
      <div className="graph-3d-hint">拖拽旋转 · 滚轮缩放 · 点击节点查看详情</div>
    </div>
  )
}
