import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface UiState {
  navCollapsed: boolean;
  chatSidebarCollapsed: boolean;
  toggleNav: () => void;
  toggleChatSidebar: () => void;
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      navCollapsed: false,
      chatSidebarCollapsed: false,
      toggleNav: () => set((s) => ({ navCollapsed: !s.navCollapsed })),
      toggleChatSidebar: () => set((s) => ({ chatSidebarCollapsed: !s.chatSidebarCollapsed })),
    }),
    { name: 'sc.ui.v1' },
  ),
);
