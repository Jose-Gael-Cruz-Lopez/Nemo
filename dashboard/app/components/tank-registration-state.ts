/** Registration is an additive gate; candidate overlays never admit measurements. */
import { invertMatrix, type WaterMapping } from "./camera-grid-state.ts";
import { parseCalibration, type CalibrationReport } from "./field-workflow-state.ts";

export type RegistrationStatus = {
  state: "NO_REFERENCE" | "CANDIDATE_MAPPING" | "VALIDATION_FAILED" | "STABLE_APPROVED" | "MOVED_STALE";
  reason: string; proposal_id: string | null; ready_for_approval: boolean; mapping_current: boolean;
  data_origin: "SYNTHETIC" | "OPERATOR_SURVEYED"; physical_accuracy_validated: false;
  proposal: { calibration: CalibrationReport; fit_pixels: number[][]; water_polygon_px: number[][] } | null;
  geometry_layers: Record<string, { status: string; operator_confirmed?: boolean; candidates?: { polygon_px: number[][]; polygon_cm: number[][] }[] }>;
  calibration_id: string | null;
};
export function parseRegistration(value: unknown): RegistrationStatus {
  if (!value || typeof value !== "object") throw new Error("Invalid registration response");
  const row = value as RegistrationStatus;
  if (!["NO_REFERENCE", "CANDIDATE_MAPPING", "VALIDATION_FAILED", "STABLE_APPROVED", "MOVED_STALE"].includes(row.state)
      || typeof row.reason !== "string" || typeof row.mapping_current !== "boolean"
      || typeof row.ready_for_approval !== "boolean" || row.physical_accuracy_validated !== false
      || !["SYNTHETIC", "OPERATOR_SURVEYED"].includes(row.data_origin)
      || row.proposal_id !== null && !/^[a-f0-9]{64}$/.test(row.proposal_id)
      || !row.geometry_layers || typeof row.geometry_layers !== "object") throw new Error("Unsupported registration state");
  if (row.mapping_current !== (row.state === "STABLE_APPROVED") || row.state === "MOVED_STALE" && row.proposal !== null) throw new Error("Contradictory registration approval");
  if (row.proposal) {
    const c = row.proposal.calibration;
    parseCalibration(c, row.proposal.fit_pixels);
    if (!c.approved || c.validation_count < 3 || c.max_error_cm < 0 || c.mean_error_cm < 0 || c.mean_error_cm > c.max_error_cm || c.max_allowed_error_cm <= 0 || c.max_allowed_error_cm > 0.5 || c.max_error_cm > c.max_allowed_error_cm) throw new Error("Independent registration checks failed");
    if (!invertMatrix(c.homography_image_to_cm) || !Array.isArray(row.proposal.water_polygon_px)
        || row.proposal.water_polygon_px.length < 3 || row.proposal.water_polygon_px.length > 32
        || row.proposal.water_polygon_px.some(p => !Array.isArray(p) || p.length !== 2 || !p.every(Number.isFinite))) throw new Error("Invalid registration support polygon");
  }
  if (row.mapping_current && (!row.proposal || row.calibration_id !== row.proposal.calibration.calibration_id)) throw new Error("Registration mapping ID mismatch");
  return row;
}
export function registrationMapping(status: RegistrationStatus | null): WaterMapping | null {
  if (!status?.proposal || status.state === "MOVED_STALE") return null;
  const c = status.proposal.calibration;
  return { ...c, approved: status.mapping_current, estimated: !status.mapping_current,
    plane: status.mapping_current ? "measured_water_surface" : "estimated_water_surface",
    mapping_polygon_px: status.proposal.fit_pixels, water_region_polygon_px: status.proposal.water_polygon_px };
}
export const registrationStage = [
  { title: "1. Detect and check", description: "Seven identifiable references supply known scale. Four IDs fit the mapping; three separate IDs check it. The grid is clipped to the declared water outline." },
  { title: "2. Camera bump → withhold", description: "The picture moves. The old grid disappears and centimetre analysis is withheld. The frozen matrix is not silently refitted." },
  { title: "3. Propose recovery", description: "A fresh proposal follows the moved references. Independent checks pass again, but the candidate still needs operator approval. Flow validation remains separate." },
  { title: "4. Lose a reference → withhold", description: "One reference is no longer readable. The mapping becomes stale again; pixel preview may continue, but scientific recording cannot." },
];
