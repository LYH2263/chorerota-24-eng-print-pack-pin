<template>
  <div class="shell">
    <main class="main"><router-view /></main>
    <nav class="bottom-tabs">
      <router-link to="/">本周</router-link>
      <router-link to="/members">成员</router-link>
      <router-link to="/tasks">任务</router-link>
      <router-link to="/swaps">对调</router-link>
      <router-link to="/settings">设置</router-link>
    </nav>
  </div>
</template>
