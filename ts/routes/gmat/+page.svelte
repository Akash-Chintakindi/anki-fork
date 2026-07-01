<!--
Copyright: GMATWiz contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
-->
<script lang="ts">
    import type { PageData } from "./$types";
    import GmatApp from "./GmatApp.svelte";

    export let data: PageData;
</script>

<GmatApp overview={data.overview} />
