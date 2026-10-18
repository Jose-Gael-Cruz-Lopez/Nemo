/** Static reduced-motion/no-WebGL fallback from the actual supplied dot lattice.
 * Uses the same Three camera, framing and orientation; it is illustrative.
 */
import { writeFileSync } from "node:fs";
import sharp from "sharp";
import * as THREE from "three";
import { scatterLandDots } from "../../app/components/atomic-globe-runtime.mjs";

const size = 189, fov = 45, cameraZ = 3.5;
const camera = new THREE.PerspectiveCamera(fov, 1, .1, 80);
camera.position.z = cameraZ;
camera.updateMatrixWorld();
const scale = 2 * Math.tan(fov * Math.PI / 360) * cameraZ / 2.6 * .9;
const matrix = new THREE.Matrix4().makeRotationFromEuler(new THREE.Euler(18 * Math.PI / 180, 15 * Math.PI / 180, 0));
const dots = scatterLandDots(8000), circles = [];
for (let index = 0; index < dots.count; index++) {
  const point = new THREE.Vector3().fromArray(dots.position, index * 3).applyMatrix4(matrix);
  const front = Math.max(0, Math.min(1, (point.z + .22) / .5));
  const alpha = .14 + .86 * front * front * (3 - 2 * front);
  const screen = point.multiplyScalar(scale).project(camera);
  circles.push(`<circle cx="${((screen.x + 1) * size / 2).toFixed(3)}" cy="${((1 - screen.y) * size / 2).toFixed(3)}" r=".54" opacity="${(alpha * .8).toFixed(3)}"/>`);
}
const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}"><g fill="#f4fbff">${circles.join("")}</g></svg>`;
const png = await sharp(Buffer.from(svg)).png().toBuffer();
writeFileSync(new URL("../../public/geo/atomic-globe-fallback.png", import.meta.url), png);
console.log(JSON.stringify({ size, dots: dots.count, bytes: png.length }));
