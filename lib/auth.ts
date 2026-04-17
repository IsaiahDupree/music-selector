import { supabaseClient, supabaseAdmin } from "./supabase";

/**
 * Sign up with email and password
 */
export async function signUp(email: string, password: string) {
  if (!supabaseClient) {
    return { success: false, error: "Database not configured" };
  }
  try {
    const { data, error } = await supabaseClient.auth.signUp({
      email,
      password,
    });

    if (error) {
      return { success: false, error: error.message };
    }

    return {
      success: true,
      user: data.user,
      session: data.session,
    };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Unknown error",
    };
  }
}

/**
 * Sign in with email and password
 */
export async function signIn(email: string, password: string) {
  if (!supabaseClient) {
    return { success: false, error: "Database not configured" };
  }
  try {
    const { data, error } = await supabaseClient.auth.signInWithPassword({
      email,
      password,
    });

    if (error) {
      return { success: false, error: error.message };
    }

    return {
      success: true,
      user: data.user,
      session: data.session,
    };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Unknown error",
    };
  }
}

/**
 * Sign out current user
 */
export async function signOut() {
  if (!supabaseClient) {
    return { success: false, error: "Database not configured" };
  }
  try {
    const { error } = await supabaseClient.auth.signOut();

    if (error) {
      return { success: false, error: error.message };
    }

    return { success: true };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Unknown error",
    };
  }
}

/**
 * Get current user session
 */
export async function getSession() {
  if (!supabaseClient) {
    return { success: false, error: "Database not configured" };
  }
  try {
    const { data, error } = await supabaseClient.auth.getSession();

    if (error) {
      return { success: false, error: error.message };
    }

    return {
      success: true,
      session: data.session,
      user: data.session?.user,
    };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Unknown error",
    };
  }
}

/**
 * Verify JWT token (server-side)
 */
export async function verifyToken(token: string) {
  if (!supabaseAdmin) {
    return { success: false, error: "Admin client not available" };
  }

  try {
    const { data, error } = await supabaseAdmin.auth.getUser(token);

    if (error) {
      return { success: false, error: error.message };
    }

    return {
      success: true,
      user: data.user,
    };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Unknown error",
    };
  }
}

/**
 * Reset password
 */
export async function resetPassword(email: string) {
  if (!supabaseClient) {
    return { success: false, error: "Database not configured" };
  }
  try {
    const { error } = await supabaseClient.auth.resetPasswordForEmail(email);

    if (error) {
      return { success: false, error: error.message };
    }

    return { success: true };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Unknown error",
    };
  }
}
