import type { Profile } from "../api/contracts";

export function profileInitials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}

type AvatarSource = Pick<Profile, "name" | "color" | "avatar">;

/** Avatar rond : photo si elle existe, sinon initiales sur la couleur du profil. */
export function ProfileAvatar({ profile, size = 56 }: { profile: AvatarSource; size?: number }) {
  const style = { width: size, height: size, fontSize: Math.round(size * 0.36) };
  if (profile.avatar) {
    return <img alt="" className="profile-avatar profile-avatar--photo" src={profile.avatar} style={style} />;
  }
  return (
    <span aria-hidden="true" className="profile-avatar" style={{ ...style, background: profile.color }}>
      {profileInitials(profile.name)}
    </span>
  );
}
