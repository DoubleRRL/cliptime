"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Separator } from "@/components/ui/separator";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { signOut } from "@/lib/auth-client";
import { track } from "@/lib/datafast";
import { isLocalSingleUserMode } from "@/lib/app-flags";
import { useEffectiveSession } from "@/hooks/use-effective-session";
import Link from "next/link";
import { Type, Palette, CheckCircle, AlertCircle, Settings, ArrowLeft } from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";
import { ModelSelector } from "@/components/model-selector";

interface UserPreferences {
  fontFamily: string;
  fontSize: number;
  fontColor: string;
  captionTemplate: string;
  llmModel: string | null;
}

interface CaptionTemplateOption {
  id: string;
  name: string;
}

export default function SettingsPage() {
  const [fontFamily, setFontFamily] = useState("TikTokSans-Regular");
  const [fontSize, setFontSize] = useState(24);
  const [fontColor, setFontColor] = useState("#FFFFFF");
  const [captionTemplate, setCaptionTemplate] = useState("default");
  const [llmModel, setLlmModel] = useState<string | null>(null);
  const [availableTemplates, setAvailableTemplates] = useState<CaptionTemplateOption[]>([]);
  const [availableFonts, setAvailableFonts] = useState<Array<{ name: string, display_name: string }>>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isFetching, setIsFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const { user, isPending } = useEffectiveSession();
  const isAdmin = Boolean(user?.is_admin);

  // Load available fonts from backend and inject them into the page
  useEffect(() => {
    const loadFonts = async () => {
      try {
        const response = await fetch('/api/fonts', { cache: 'no-store' });
        if (response.ok) {
          const data = await response.json();
          setAvailableFonts(data.fonts || []);

          // Dynamically load fonts using @font-face
          const fontFaceStyles = data.fonts.map((font: { name: string }) => {
            return `
              @font-face {
                font-family: '${font.name}';
                src: url('/api/fonts/${font.name}') format('truetype');
                font-weight: normal;
                font-style: normal;
              }
            `;
          }).join('\n');

          // Inject font styles into the page
          const styleElement = document.createElement('style');
          styleElement.id = 'custom-fonts';
          styleElement.innerHTML = fontFaceStyles;

          // Remove existing custom fonts style if present
          const existingStyle = document.getElementById('custom-fonts');
          if (existingStyle) {
            existingStyle.remove();
          }

          document.head.appendChild(styleElement);
        }
      } catch (error) {
        console.error('Failed to load fonts:', error);
      }
    };

    loadFonts();
  }, []);

  useEffect(() => {
    const loadTemplates = async () => {
      try {
        const response = await fetch("/api/caption-templates");
        if (response.ok) {
          const data = await response.json();
          setAvailableTemplates(data.templates || []);
        }
      } catch (loadError) {
        console.error("Failed to load caption templates:", loadError);
      }
    };

    loadTemplates();
  }, []);

  // Load user preferences
  useEffect(() => {
    const loadPreferences = async () => {
      if (!user?.id) return;

      setIsFetching(true);
      try {
        const response = await fetch('/api/preferences');
        if (response.ok) {
          const data: UserPreferences = await response.json();
          setFontFamily(data.fontFamily);
          setFontSize(data.fontSize);
          setFontColor(data.fontColor);
          setCaptionTemplate(data.captionTemplate || "default");
          setLlmModel(data.llmModel ?? null);
        }
      } catch (error) {
        console.error('Failed to load preferences:', error);
      } finally {
        setIsFetching(false);
      }
    };

    loadPreferences();
  }, [user?.id]);

  const handleSavePreferences = async () => {
    setIsLoading(true);
    setError(null);
    setSuccess(false);

    try {
      const response = await fetch('/api/preferences', {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          fontFamily,
          fontSize,
          fontColor,
          captionTemplate,
          llmModel,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to save preferences');
      }

      track("preferences_saved");
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (error) {
      console.error('Error saving preferences:', error);
      setError(error instanceof Error ? error.message : 'Failed to save preferences');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSignOut = async () => {
    await signOut();
    window.location.href = "/sign-in";
  };

  if (isPending || isFetching) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <div className="space-y-4">
          <Skeleton className="h-4 w-32 mx-auto" />
          <Skeleton className="h-4 w-48 mx-auto" />
          <Skeleton className="h-4 w-24 mx-auto" />
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="min-h-screen bg-background">
        <div className="max-w-4xl mx-auto px-4 py-24">
          <div className="text-center">
            <h1 className="text-3xl font-bold text-foreground mb-4">
              Sign In Required
            </h1>
            <p className="text-muted-foreground mb-8">
              You need to sign in to access your settings
            </p>
            <Link href="/sign-in">
              <Button size="lg">Sign In</Button>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b border-border bg-background">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex justify-between items-center">
            <Link href="/">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="w-4 h-4" />
                Back
              </Button>
            </Link>

            <div className="flex items-center gap-3">
              <ThemeToggle />
              {isAdmin && (
                <Link href="/admin">
                  <Button variant="outline" size="sm">
                    Admin
                  </Button>
                </Link>
              )}
              {!isLocalSingleUserMode && (
                <Button variant="outline" size="sm" onClick={handleSignOut}>
                  Sign Out
                </Button>
              )}
              <Avatar className="w-8 h-8">
                <AvatarImage src="" />
                <AvatarFallback className="bg-muted text-foreground text-sm">
                  {user.name?.charAt(0) || user.email?.charAt(0) || "U"}
                </AvatarFallback>
              </Avatar>
              <div className="hidden sm:block">
                <p className="text-sm font-medium text-foreground">{user.name}</p>
                <p className="text-xs text-muted-foreground">{user.email}</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-4xl mx-auto px-4 py-16">
        <div className="max-w-xl mx-auto">
          <div className="mb-8">
            <div className="flex items-center gap-2 mb-2">
              <Settings className="w-6 h-6 text-foreground" />
              <h2 className="text-2xl font-bold text-foreground">
                Settings
              </h2>
            </div>
            <p className="text-muted-foreground">
              Configure your default preferences for video clip generation
            </p>
          </div>

          <Separator className="my-8" />

          <div className="space-y-8">
            {/* Font Preferences Section */}
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-semibold text-foreground mb-1">
                  Default Font Settings
                </h3>
                <p className="text-sm text-muted-foreground">
                  These settings will be applied to all new video processing tasks
                </p>
              </div>

              {/* Font Family Selector */}
              <div className="space-y-2">
                <Label className="text-sm font-medium text-foreground flex items-center gap-2">
                  <Type className="w-4 h-4" />
                  Font Family
                </Label>
                <Select value={fontFamily} onValueChange={setFontFamily} disabled={isLoading}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select font" />
                  </SelectTrigger>
                  <SelectContent>
                    {availableFonts.map((font) => (
                      <SelectItem key={font.name} value={font.name}>
                        {font.display_name}
                      </SelectItem>
                    ))}
                    {availableFonts.length === 0 && (
                      <SelectItem value="TikTokSans-Regular">TikTok Sans Regular</SelectItem>
                    )}
                  </SelectContent>
                </Select>
              </div>

              {/* Font Size Slider */}
              <div className="space-y-2">
                <Label className="text-sm font-medium text-foreground">
                  Font Size: {fontSize}px
                </Label>
                <div className="px-2">
                  <Slider
                    value={[fontSize]}
                    onValueChange={(value) => setFontSize(value[0])}
                    max={48}
                    min={12}
                    step={2}
                    disabled={isLoading}
                    className="w-full"
                  />
                </div>
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>12px</span>
                  <span>48px</span>
                </div>
              </div>

              {/* Caption Template */}
              <div className="space-y-2">
                <Label className="text-sm font-medium text-foreground">
                  Default Caption Style
                </Label>
                <Select value={captionTemplate} onValueChange={setCaptionTemplate} disabled={isLoading}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select caption style" />
                  </SelectTrigger>
                  <SelectContent>
                    {availableTemplates.map((template) => (
                      <SelectItem key={template.id} value={template.id}>
                        {template.name}
                      </SelectItem>
                    ))}
                    {availableTemplates.length === 0 && (
                      <SelectItem value="default">Default</SelectItem>
                    )}
                  </SelectContent>
                </Select>
              </div>

              {/* Font Color Picker */}
              <div className="space-y-2">
                <Label className="text-sm font-medium text-foreground flex items-center gap-2">
                  <Palette className="w-4 h-4" />
                  Font Color
                </Label>
                <div className="flex items-center gap-2">
                  <input
                    type="color"
                    value={fontColor}
                    onChange={(e) => setFontColor(e.target.value)}
                    disabled={isLoading}
                    className="w-12 h-10 rounded border border-border cursor-pointer disabled:cursor-not-allowed"
                  />
                  <Input
                    type="text"
                    value={fontColor}
                    onChange={(e) => setFontColor(e.target.value)}
                    disabled={isLoading}
                    placeholder="#FFFFFF"
                    className="flex-1 h-10"
                    pattern="^#[0-9A-Fa-f]{6}$"
                  />
                </div>
                <div className="flex gap-2 mt-2">
                  {["#FFFFFF", "#000000", "#FFD700", "#FF6B6B", "#4ECDC4", "#45B7D1"].map((color) => (
                    <button
                      key={color}
                      type="button"
                      onClick={() => setFontColor(color)}
                      disabled={isLoading}
                      className="w-8 h-8 rounded border-2 border-border cursor-pointer hover:scale-110 transition-transform disabled:cursor-not-allowed"
                      style={{ backgroundColor: color }}
                      title={color}
                    />
                  ))}
                </div>
              </div>

              {/* Default AI model */}
              <div className="space-y-2">
                <Label className="text-sm font-medium text-foreground">
                  Default AI Model
                </Label>
                <ModelSelector value={llmModel} onChange={setLlmModel} disabled={isLoading} />
                <p className="text-xs text-muted-foreground">
                  Used for clip selection on new sessions. Install recommended models with one click —
                  you can still override this per session.
                </p>
              </div>

              {/* Preview */}
              <div className="space-y-2">
                <Label className="text-sm font-medium text-foreground">Preview</Label>
                <div className="p-6 bg-black rounded-lg flex items-center justify-center min-h-[100px]">
                  <p
                    style={{
                      color: fontColor,
                      fontSize: `${Math.min(fontSize, 32)}px`,
                      fontFamily: `'${fontFamily}', system-ui, -apple-system, sans-serif`,
                      textAlign: 'center',
                      lineHeight: '1.4'
                    }}
                    className="font-medium"
                  >
                    Your subtitle will look like this
                  </p>
                </div>
              </div>
            </div>

            <Separator className="mb-4" />

            {/* Success/Error Messages */}
            {success && (
              <Alert className="border-green-500/20 bg-green-500/10">
                <CheckCircle className="h-4 w-4 text-green-400" />
                <AlertDescription className="text-sm text-green-400">
                  Preferences saved successfully!
                </AlertDescription>
              </Alert>
            )}

            {error && (
              <Alert className="border-red-500/20 bg-red-500/10">
                <AlertCircle className="h-4 w-4 text-red-400" />
                <AlertDescription className="text-sm text-red-400">
                  {error}
                </AlertDescription>
              </Alert>
            )}

            {/* Save Button */}
            <Button
              onClick={handleSavePreferences}
              disabled={isLoading}
              className="w-full h-11"
            >
              {isLoading ? "Saving..." : "Save Preferences"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
