// Run from the portfolio repo root, or adjust the path.
import { buildCarParticles, SENSOR } from "./lib/particles/car.ts";
const p = buildCarParticles(2600);
await Bun.write(process.argv[2], JSON.stringify({ sensor: SENSOR, points: p.map(q => [q.car.x, q.car.y, q.car.z, q.phase, q.tone]) }));
