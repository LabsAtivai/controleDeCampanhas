import { ref } from 'vue';

export const notifications = ref([]);
let nextId = 0;
export function notify(message, tone = 'success') {
  const id = ++nextId;
  notifications.value.push({ id, message, tone });
  setTimeout(() => {
    notifications.value = notifications.value.filter((item) => item.id !== id);
  }, 6000);
}
