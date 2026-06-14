import { NextRequest, NextResponse } from "next/server";
import { getPrismaClient } from "@/server/prisma";
import { getEffectiveSession } from "@/server/session";

const HEX_6 = /^#[0-9A-Fa-f]{6}$/;
const HEX_8 = /^#[0-9A-Fa-f]{8}$/;

function isHexColor(value: string): boolean {
  return HEX_6.test(value) || HEX_8.test(value);
}

// GET /api/preferences - Get user preferences
export async function GET(_: NextRequest) {
  try {
    const session = await getEffectiveSession();

    if (!session?.user?.id) {
      return NextResponse.json(
        { error: "Unauthorized" },
        { status: 401 }
      );
    }

    const prisma = getPrismaClient();
    const user = await prisma.user.findUnique({
      where: { id: session.user.id },
      select: {
        default_font_family: true,
        default_font_size: true,
        default_font_color: true,
        default_highlight_color: true,
        default_pill_color: true,
        default_caption_template: true,
        default_llm_model: true,
      },
    });

    if (!user) {
      return NextResponse.json(
        { error: "User not found" },
        { status: 404 }
      );
    }

    return NextResponse.json({
      fontFamily: user.default_font_family || "TikTokSans-Regular",
      fontSize: user.default_font_size || 32,
      fontColor: user.default_font_color || "#FFFFFF",
      highlightColor: user.default_highlight_color || "#8B5CF6",
      pillColor: user.default_pill_color || "#1A1A1ACC",
      captionTemplate: user.default_caption_template || "riverside",
      llmModel: user.default_llm_model || null,
    });
  } catch (error) {
    console.error("Error fetching preferences:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}

// PATCH /api/preferences - Update user preferences
export async function PATCH(request: NextRequest) {
  try {
    const session = await getEffectiveSession();

    if (!session?.user?.id) {
      return NextResponse.json(
        { error: "Unauthorized" },
        { status: 401 }
      );
    }

    const body = await request.json();
    const {
      fontFamily,
      fontSize,
      fontColor,
      highlightColor,
      pillColor,
      captionTemplate,
      llmModel,
    } = body;

    if (fontFamily && typeof fontFamily !== "string") {
      return NextResponse.json(
        { error: "Invalid fontFamily" },
        { status: 400 }
      );
    }

    if (fontSize && (typeof fontSize !== "number" || fontSize < 12 || fontSize > 48)) {
      return NextResponse.json(
        { error: "Invalid fontSize (must be between 12 and 48)" },
        { status: 400 }
      );
    }

    if (fontColor && !HEX_6.test(fontColor)) {
      return NextResponse.json(
        { error: "Invalid fontColor (must be hex format like #FFFFFF)" },
        { status: 400 }
      );
    }

    if (highlightColor && !isHexColor(highlightColor)) {
      return NextResponse.json(
        { error: "Invalid highlightColor" },
        { status: 400 }
      );
    }

    if (pillColor && !isHexColor(pillColor)) {
      return NextResponse.json(
        { error: "Invalid pillColor" },
        { status: 400 }
      );
    }

    if (
      captionTemplate !== undefined &&
      (typeof captionTemplate !== "string" || captionTemplate.length > 50)
    ) {
      return NextResponse.json(
        { error: "Invalid captionTemplate" },
        { status: 400 }
      );
    }

    if (
      llmModel !== undefined &&
      llmModel !== null &&
      (typeof llmModel !== "string" || llmModel.length > 200)
    ) {
      return NextResponse.json(
        { error: "Invalid llmModel" },
        { status: 400 }
      );
    }

    const prisma = getPrismaClient();
    const updatedUser = await prisma.user.update({
      where: { id: session.user.id },
      data: {
        ...(fontFamily !== undefined && { default_font_family: fontFamily }),
        ...(fontSize !== undefined && { default_font_size: fontSize }),
        ...(fontColor !== undefined && { default_font_color: fontColor }),
        ...(highlightColor !== undefined && { default_highlight_color: highlightColor }),
        ...(pillColor !== undefined && { default_pill_color: pillColor }),
        ...(captionTemplate !== undefined && { default_caption_template: captionTemplate }),
        ...(llmModel !== undefined && { default_llm_model: llmModel }),
      },
      select: {
        default_font_family: true,
        default_font_size: true,
        default_font_color: true,
        default_highlight_color: true,
        default_pill_color: true,
        default_caption_template: true,
        default_llm_model: true,
      },
    });

    return NextResponse.json({
      fontFamily: updatedUser.default_font_family,
      fontSize: updatedUser.default_font_size,
      fontColor: updatedUser.default_font_color,
      highlightColor: updatedUser.default_highlight_color,
      pillColor: updatedUser.default_pill_color,
      captionTemplate: updatedUser.default_caption_template,
      llmModel: updatedUser.default_llm_model,
    });
  } catch (error) {
    console.error("Error updating preferences:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
