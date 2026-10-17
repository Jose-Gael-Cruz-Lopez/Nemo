import { showcaseGet, showcaseWriteBlocked } from "../../../../../../showcase/report";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export function GET(request: Request) { return showcaseGet(request); }
export function POST() { return showcaseWriteBlocked(); }
