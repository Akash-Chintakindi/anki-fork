// Copyright: GMATWiz contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
import type { PageLoad } from "./$types";

import { fetchOverview } from "./api";

export const load = (async () => {
    const overview = await fetchOverview();
    return { overview };
}) satisfies PageLoad;
