<!--
Copyright: GMATWiz contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
-->
<script lang="ts">
    import type { PageData } from "./$types";
    import GmatPracticePage from "./GmatPracticePage.svelte";

    export let data: PageData;
</script>

<GmatPracticePage questions={data.questions} />
