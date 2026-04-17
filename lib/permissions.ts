/**
 * Permissions and Authorization
 * Role-based access control for music library
 */

export type UserRole = 'owner' | 'editor' | 'viewer' | 'guest';

export interface UserPermissions {
  canRead: boolean;
  canCreate: boolean;
  canUpdate: boolean;
  canDelete: boolean;
  canShare: boolean;
  canExport: boolean;
  canManageUsers: boolean;
}

export interface LibraryAccess {
  userId: string;
  libraryId: string;
  role: UserRole;
  createdAt: string;
}

/**
 * Get permissions for a given role
 */
export function getPermissionsForRole(role: UserRole): UserPermissions {
  const permissionsByRole: Record<UserRole, UserPermissions> = {
    owner: {
      canRead: true,
      canCreate: true,
      canUpdate: true,
      canDelete: true,
      canShare: true,
      canExport: true,
      canManageUsers: true,
    },
    editor: {
      canRead: true,
      canCreate: true,
      canUpdate: true,
      canDelete: true,
      canShare: false,
      canExport: true,
      canManageUsers: false,
    },
    viewer: {
      canRead: true,
      canCreate: false,
      canUpdate: false,
      canDelete: false,
      canShare: false,
      canExport: true,
      canManageUsers: false,
    },
    guest: {
      canRead: true,
      canCreate: false,
      canUpdate: false,
      canDelete: false,
      canShare: false,
      canExport: false,
      canManageUsers: false,
    },
  };

  return permissionsByRole[role];
}

/**
 * Check if user has specific permission
 */
export function userHasPermission(
  role: UserRole,
  permission: keyof UserPermissions
): boolean {
  const permissions = getPermissionsForRole(role);
  return permissions[permission] === true;
}

/**
 * Verify user can perform action
 */
export function verifyUserPermission(
  role: UserRole,
  requiredPermission: keyof UserPermissions
): void {
  if (!userHasPermission(role, requiredPermission)) {
    throw new Error(`User with role '${role}' does not have ${requiredPermission} permission`);
  }
}

/**
 * Create RLS (Row Level Security) policy string for Supabase
 */
export function createRLSPolicy(
  userId: string,
  libraryId: string,
  role: UserRole
): Record<string, any> {
  return {
    user_id: userId,
    library_id: libraryId,
    role: role,
  };
}

/**
 * Check if user owns the library
 */
export function isLibraryOwner(
  userId: string,
  libraryOwnerId: string
): boolean {
  return userId === libraryOwnerId;
}

/**
 * Get list of users who can perform action on track
 */
export function getAuthorizedUsers(
  trackOwnerId: string,
  requiredRole: UserRole,
  sharedWith: LibraryAccess[]
): string[] {
  const authorizedUsers = [trackOwnerId];

  // Add users with at least the required role
  const roleHierarchy = { guest: 0, viewer: 1, editor: 2, owner: 3 };
  const requiredLevel = roleHierarchy[requiredRole];

  sharedWith.forEach(access => {
    const userLevel = roleHierarchy[access.role];
    if (userLevel >= requiredLevel) {
      authorizedUsers.push(access.userId);
    }
  });

  return [...new Set(authorizedUsers)]; // Remove duplicates
}

/**
 * Validate library access for user
 */
export function validateLibraryAccess(
  userId: string,
  libraryOwnerId: string,
  requiredRole: UserRole,
  userAccess: LibraryAccess[]
): boolean {
  // Owner always has access
  if (isLibraryOwner(userId, libraryOwnerId)) {
    return true;
  }

  // Check if user has appropriate access
  const userAccess_ = userAccess.find(a => a.userId === userId);
  if (!userAccess_) {
    return false;
  }

  // Check role hierarchy
  const roleHierarchy = { guest: 0, viewer: 1, editor: 2, owner: 3 };
  const userLevel = roleHierarchy[userAccess_.role];
  const requiredLevel = roleHierarchy[requiredRole];

  return userLevel >= requiredLevel;
}

/**
 * Sanitize library data for user role
 */
export function sanitizeLibraryData(
  data: Record<string, any>,
  userRole: UserRole
): Record<string, any> {
  const permissions = getPermissionsForRole(userRole);

  const sanitized = { ...data };

  // Remove sensitive data based on permissions
  if (!permissions.canManageUsers) {
    delete sanitized.users;
    delete sanitized.sharedWith;
  }

  if (!permissions.canDelete) {
    delete sanitized.deletionToken;
  }

  return sanitized;
}
