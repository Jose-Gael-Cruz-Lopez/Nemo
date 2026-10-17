type EvidenceIdentity = { id: string; case_id: string };

/** Only expose a report belonging to the case's current immutable evidence ID. */
export function currentSourceEvidence<T extends EvidenceIdentity>(
  report: T | null | undefined,
  caseId: string,
  evidenceId: string | null | undefined,
): T | null {
  return report && caseId && evidenceId && report.case_id === caseId && report.id === evidenceId
    ? report
    : null;
}

/** Read-only recovery is available only for a current failed read, one attempt at a time. */
export function canReloadSourceEvidence(
  failure: EvidenceIdentity | null | undefined,
  caseId: string,
  evidenceId: string | null | undefined,
  pending: boolean,
): boolean {
  return !pending && currentSourceEvidence(failure, caseId, evidenceId) !== null;
}
