import axios from "axios";

import { getGalaxyInstance } from "@/app";
import { useAuthStore } from "@/stores/authStore";
import { withPrefix } from "@/utils/redirect";

/**
 * Handles user logout.  Invalidates the current session, checks to see if we
 * need to log out of OIDC too, and goes to our POST_LOGOUT_URL (or some other
 * configured redirect). */
export function userLogout(logoutAll = false) {
    const Galaxy = getGalaxyInstance();
    const authStore = useAuthStore();
    const post_user_logout_href = Galaxy.config.post_user_logout_href;
    authStore
        .logout(logoutAll)
        .then((response) => {
            if (Galaxy.config.enable_oidc) {
                return axios.get(withPrefix("/authnz/logout"));
            }
            return response;
        })
        .then((response) => {
            const redirectUri = response.redirect_uri || response.data?.redirect_uri;
            if (redirectUri) {
                window.top.location.href = redirectUri;
            } else {
                window.top.location.href = withPrefix(post_user_logout_href);
            }
        });
}

/** User logout with 'log out all sessions' flag set.  This will invalidate all
 * active sessions a user might have. */
export function userLogoutAll() {
    return userLogout(true);
}

/** Purely clientside logout, dumps session and redirects without invalidating
 * serverside. Currently only used when marking an account deleted -- any
 * subsequent navigation after the deletion API request would fail otherwise */
export function userLogoutClient() {
    const Galaxy = getGalaxyInstance();
    const authStore = useAuthStore();
    authStore.clearAuthState();
    const post_user_logout_href = Galaxy.config.post_user_logout_href;
    window.top.location.href = withPrefix(post_user_logout_href);
}
